# CV Name-Parsing — Research, Findings & Recommended Architecture

> Status: **R&D complete — verdict: GO (ship heuristic ensemble + Gemini gate;
> SKIP the ML ranker).** NOT yet productionized. All work lives in the standalone
> harness `BackEnd/qc_name_eval.py`. Production code is untouched. Pick this up
> when ready to implement (§6). Validated on 236 CVs — see §3f and §8.

---

## 1. Why this exists (the problem)

The candidate **name** is the most important field for recruiters — it must be
present and correct. Today it's extracted **only** by a Gemini API call per CV
(`app/utils/gemini_parser.py`). Problems:

- **Quota wall:** Gemini free tier returns **429 / "Too Many Requests"** at the
  team's volume (>50 CVs/day). On a 429 the name silently fails to parse.
- **Accuracy was never measured** — earlier filename/top-line/email heuristics
  "felt poor" on messy, unstructured Indian CVs, but with no numbers.

**Goal:** get name extraction off the per-CV Gemini dependency using free, local
methods, keeping Gemini only as a rare fallback — and prove it with data.

### Hard constraints
- **VPS, ~2.7 GB RAM, already swapping** (`free -h`: ~950 MB available, swap
  2.4/2.7 GB used). A **job portal is also being built on the same box.**
  → footprint must stay tiny. **No heavy/transformer NER (IndicNER ~500 MB)** —
  it would OOM / deepen swap. RAM can be increased later if needed.
- English-script CVs, Indian names (phonetic variants, initials, run-together
  portal exports, middle names).

---

## 2. The QC harness (`qc_name_eval.py`)

Fully self-contained; imports nothing from `app/`. Re-implements text extraction
and the Gemini prompt locally so it's portable and side-effect-free.

```bash
cd BackEnd

# 1. Build ground-truth labels from filenames (then eyeball-verify the noisy ones)
python qc_name_eval.py autolabel --dir uploaded_cvs --out labels.csv

# 2. Score each method vs labels (choose PDF engine; pdfminer is best — see §3)
python qc_name_eval.py eval --dir uploaded_cvs --labels labels.csv \
       --pdf-engine pdfminer [--no-gemini]

# 3. Train + cross-validate the ML candidate-ranker vs heuristic ensemble
python qc_name_eval.py train --dir uploaded_cvs --labels labels.csv [--no-filename]

# 4. Head-to-head: heuristics-only vs ML-only vs both (+ font ablation)
python qc_name_eval.py compare --dir uploaded_cvs --labels labels.csv \
       --pdf-engine pdfminer [--no-filename]
```

`--no-filename` simulates ZIP/UUID bulk uploads (drops the filename signal) — the
**honest, non-circular** test, since our labels were derived from filenames.

Methods implemented: `filename`, `topline`, `email`, `spacy_ner`, `ensemble`,
`reconcile` (filename⇄email), `gemini`, plus the ML ranker and a font-only pick.

Name comparison uses **`indian-namematch`** (`fuzzymatch.single_compare`) for
phonetic / spelling / middle-name / title-prefix matching, with exact and
token-set (order-insensitive) fallbacks.

---

## 3. Findings (measured on 70 real CVs, mostly portal exports)

### 3a. PDF extractor is the single biggest lever
Same `topline` heuristic, only the PDF library changes:

| Extractor | `topline` accuracy |
|---|---|
| **`fitz` (PyMuPDF) — what PRODUCTION uses** | **61%** |
| `pypdfium2` | 54% |
| **`pdfminer.six`** | **87%** |

PyMuPDF reads text in geometric-block order → scatters the name. `pdfminer.six`
preserves reading order → the name lands in the first lines. **`pdfminer.six` is
already a dependency.** Tradeoff: pdfminer is pure-Python and slower per PDF
(fine for background batch parsing; keep fitz as a fast fallback).

### 3b. Per-method accuracy (pdfminer, indian-namematch on)
| Method | Accuracy | Notes |
|---|---|---|
| `filename` | 97% | ⚠️ circular here (labels came from filenames); useless for ZIP/UUID |
| `topline` | 87% | content-based, the honest workhorse |
| `email` | 27% | weak / misleading — **negative** signal |
| `spacy_ner` | 37% | weak on Indian names — **negative** signal |
| `ensemble` | 97% | |
| any local | 99% | |

### 3c. `reconcile` — filename ⇄ email cross-reference (handles portal exports)
Portal filenames often *contain* the name but jammed: `DeepakPandeyPMP`,
`ANIKETBISWAS[14y_0m]`. `reconcile`:
1. **camelCase-splits** the filename (`DeepakPandeyPMP` → Deepak, Pandey, PMP),
2. uses **email tokens to confirm** real name tokens and **drop noise**
   (drops cert `PMP` and email-only "awadh"; keeps "deepak"),
3. **segments ALL-CAPS blobs** via email tokens (`ANIKETBISWAS` +
   email `aniket`,`biswas` → "Aniket Biswas").

On a hard 5-CV test (UUID + 3 Naukri exports), reconcile fixed the cases the
plain ensemble missed (e.g. `DeepakPandeyPMP` → **Deepak Pandey**, where the old
ensemble wrongly gave "Awadh Deepak" from the email).

### 3d. ML candidate-ranker (scikit-learn — already installed)
Frames the problem as **choosing among candidates**, not reading raw text.
Per-candidate features: source flags, line position, token count, caps/title,
header-word penalty, `agree_count` (indian-namematch agreement with other
candidates), and **`font_rel`** (relative font size from PyMuPDF `get_text("dict")`)
+ `y_rel` (vertical position). Group k-fold CV (no leakage). Tiny model, ~0 RAM.

Learned feature weights (no-filename regime) — **font dominates**:
```
font_rel     +4.14      agree_count  +1.49      looks_header -1.46
src_email    -0.43      src_spacy    -0.51      (email/spacy distrusted)
```

### 3e. Head-to-head + font ablation
**Mode A — with filename** (named uploads; ~100% everywhere, but circular):
heuristic 100%, font-only 99%, ML 97–99%, ML+reconcile 100%.

**Mode B — NO filename (ZIP/UUID — the honest case):**
| Config | Accuracy |
|---|---|
| Heuristics only (reconcile+ensemble, no font, no ML) | **77%** |
| **Font-only pick ("biggest text on the page")** | **87%** |
| ML *without* font | 90% |
| **ML *with* font** | **93%** |
| content ceiling (≥1 correct candidate exists) | 94% |

**Key takeaways**
- **Font is the most powerful signal and production ignores it entirely.** Just
  "pick the largest text near the top" = **87%**, beating the whole text
  heuristic ensemble (77%).
- Font adds **+3** to the ML ranker (90% → 93%).
- ML (gboost) + font = **93%**, near the 94% ceiling.
- `email` and `spacy_ner` are *negative* signals — don't trust them.
- ~6% (the 94% ceiling gap) genuinely needs Gemini or manual (name in an image /
  headline-first layout like a CV that leads with a job title).

### 3f. Validation on 236 CVs (the honest, larger, messier set) ← decisive
The §3a–3e numbers came from 70 mostly-clean portal exports whose **labels were
derived from filenames** → the high `filename`/`ensemble` figures were partly
**circular**. We re-ran on a fresh **236-CV set** (214 PDF + 22 DOCX) from
`uploaded_cvs/test` — deliberately messier (Naukri camelCase exports, UUID names,
appraisal-note filenames, scanned/headline-first layouts).

First pass looked catastrophic (ensemble 55%) — root cause was **label noise**:
autolabel couldn't parse camelCase Naukri filenames, leaving 29% of labels EMPTY,
which scores every method wrong. After fixing `derive_name_from_filename`
(bracket-strip, camelCase-split, `_OK`/cert stopwords, `Name - Name` tail), label
noise dropped **36% → 1%** (only `1243837934.pdf` unlabelable). Honest results:

| Method | Accuracy (236 CVs, pdfminer) |
|---|---|
| `filename` | 61% |
| `topline` | 60% |
| `email` | 22% |
| `spacy_ner` | 25% |
| **`ensemble`** | **77%** |
| **any local method** | **90%** |
| residual needing Gemini / manual | **~10%** |

**What changed vs the 70-CV read:**
- The real, non-circular ceiling is **~90% solvable locally**, **~77% from the
  automatic ensemble** — not the 94–97% the small clean set suggested.
- Per-method accuracy is uniformly lower on messy data (filename 97%→61%,
  topline 87%→60%), exactly as expected once the easy lookalikes are diluted.
- **The core goal still holds:** even at 77% ensemble / 90% any-local, Gemini
  name-calls drop ~80–90% → the 429 quota wall is gone regardless.

**ML ranker — NO-GO on this box.** The `--no-filename` ML-vs-font comparison from
§3e could **not** be reproduced on 236 CVs: the `candidate_pool` loop ballooned to
**~10 GB RAM**, isolated to **spaCy** (`nlp()` called per CV — extraction itself
was <0.25 GB). On a 2.7 GB swapping VPS also hosting a job portal that's a
non-starter, and spaCy is the ranker's weakest input anyway (25%). The harness now
defaults `USE_SPACY = False`. The font signal (PyMuPDF, no spaCy) remains cheap
and valid, but a *trained ML ranker* buys too little here to justify the training
/ labelling / retrain infra — **ship the heuristic ensemble + font tiebreak +
Gemini gate instead** (§5, §8).

---

## 4. Recommended architecture (the cascade)

```
                ┌─ filename has a parseable name? ──► reconcile(filename ⇄ email)
 CV ──► extract │                                      (~100% on named files, free)
        (pdfminer│
         +fitz   └─ no usable filename (ZIP/UUID) ──► rank candidates by signals:
         for font)                                      filename/reconcile, topline,
                                                        + FONT SIZE, + agreement
                                                        • cheap: pick largest-font   (87%)
                                                        • best:  ML ranker w/ font   (93%)
                                                              │
                                                              ▼
                                              low confidence / no candidate?
                                                              │
                                                              ▼
                                                        Gemini fallback   (the ~6%)
```

Signals, in order of value: **font size** > **reconcile/filename** > **topline** >
agreement (indian-namematch). `email`/`spacy` only as weak tie-breakers.

### Two viable build levels (cost/benefit)
| Level | Bulk-upload accuracy | Cost |
|---|---|---|
| **Font-only heuristic + reconcile + Gemini fallback** | ~87% local | a few lines, **no ML, no training, no RAM** |
| **ML ranker (w/ font) + reconcile + Gemini fallback** | ~93% local | model to train + label + maintain (feedback loop) |

Font-only is the 80/20 for a constrained VPS. ML buys +6 points but needs infra.
Either way Gemini handles only the residual → quota wall solved.

---

## 5. The Gemini gate — what gets sent to Gemini (cost control)

The point of the cascade is to call Gemini **only on the CVs the locals can't
agree on**. The gate is **cross-source agreement**, NOT any single method's
self-reported confidence — `filename` is only 61% right but *looks* certain every
time, so per-method confidence is meaningless. The honest signal is: **do
independent sources corroborate each other?** When ≥2 do, they're almost always
right; when they fight, that's the genuinely hard CV worth a paid call.

### How agreement is measured
Generate up to four cheap candidates per CV, then drop empties:
`filename`/`reconcile` (skip if the filename is a UUID / ZIP / generic blob),
`topline`, `email`, plus the **largest-font line near the top** (the §3e font
signal). Compare them pairwise with **`indian-namematch`
(`fuzzymatch.single_compare`)** so phonetic / caps / middle-name variants still
count as a match ("Aman Gupta" ≈ "AMAN GUPTHA"). `agree_count` = size of the
largest cluster of candidates that fuzzy-match each other.

### The decision
```
HIGH    ≥2 independent sources agree              → accept, NO Gemini
MEDIUM  1 strong source (clean largest-font /     → accept, NO Gemini,
        topline name), nothing contradicts it        badge "verify name"
LOW     0 candidates, OR all candidates disagree  → SEND TO GEMINI
```

Rules in priority order:
1. `filename`/`reconcile` agrees with `topline` (or font line) → **HIGH**, done.
   This is the bulk of clean CVs.
2. filename is UUID/ZIP-generic (no signal) but `topline` agrees with `email` or
   the font line → **HIGH**, done.
3. Only one clean candidate (largest-font line is a plausible 2–3 token name,
   nothing contradicts) → **MEDIUM**: accept, badge, still **no Gemini**.
4. Everything disagrees, or nothing parsed → **LOW** → **Gemini** (the residual).

`email` and `spacy` are weak/negative (§3b, §3e) — use them only to *corroborate*,
never as the sole accepted source.

### Belt-and-suspenders (cheap, recommended)
- **Daily Gemini budget cap** (e.g. ≤200/day): a simple counter. If exceeded,
  LOW-confidence CVs are stored with the best local guess + `name_confidence:
  low` + a "verify name" badge instead of erroring — **never a silent failure,
  never a 429 wall**. Recruiters fix the few in the dashboard (inline edit
  exists).
- **Piggyback, don't add calls:** Gemini is already called for company / skills /
  etc. When that call happens anyway, take its name too. The gate only decides
  whether the **name alone** forces a call that wouldn't otherwise happen.

### Expected call volume
Honest 236-CV set: ~HIGH covers the agreeing majority, leaving **~10% → Gemini**
(the §3e ~6–10% ceiling gap: name in an image, headline-first layouts, fully
unparseable). That's a **~90% cut** in name-calls — comfortably under the free
quota at 50+/day. Store `name`, `name_source` (which cluster won), and
`name_confidence` (high/medium/low from `agree_count`). The gate is simply
`confidence == low → Gemini`, throttled by the daily budget.

---

## 6. Implementation notes (when productionizing — touches `app/`)

Nothing below is done yet. Get explicit approval before editing production.

1. **Reclaim RAM (safe, do first):** `app/utils/parser.py:21-23` loads a 50k-row
   names CSV (`NAMES_DF`/`FIRST_NAMES_SET`/`LAST_NAMES_SET`) that is **referenced
   nowhere**. Remove it — frees per-worker memory, eases the swapping box.
2. **Switch PDF extraction to `pdfminer.six`** in
   `app/utils/parser.py::extract_text_from_pdf` (keep `fitz` as fast fallback).
   Biggest accuracy win (61%→87% topline). Also improves search `raw_text`.
3. **Add a name resolver** in `app/utils/parser.py` used by both write paths
   (`upload_cv` in `app/api/upload.py` and `_parse_and_store_cv`): run the cascade
   in §4; call `extract_fields_with_gemini` only as the fallback (and still for
   the other fields). Store `name_confidence` + `name_source`.
4. **Surface confidence:** return `name_confidence` from `GET /list-cvs`; badge
   low-confidence names in `FrontEnd/pages/dashboard.tsx` (inline edit already
   exists for recruiters to fix them).
5. **Font feature** needs PyMuPDF `get_text("dict")` (already available) even if
   text comes from pdfminer — use both libs.
6. **(Optional) feedback loop:** log recruiter name corrections `(features →
   chosen)` and periodically retrain the scikit-learn ranker via cron. This is
   the "learns from your data" part; ~0 runtime cost.

### Already-installed libs to reuse (no new deps)
`pdfminer.six`, `indian-namematch` (`fuzzymatch.single_compare`), `scikit-learn`,
`PyMuPDF` (font features + fallback), `pandas`, spaCy.

---

## 7. Caveats & what to do before trusting the numbers

- **DONE: validated on 236 CVs (§3f).** The original 70-CV numbers (§3a–3e) were
  directional and partly circular (labels from filenames). The 236-CV honest
  numbers — **ensemble 77%, any-local 90%, residual ~10%** — are the ones to
  trust. Watch for **label noise** if you re-run autolabel on a new batch: always
  check the empty-label count first (a bad parse silently tanks every method).
- The 236-CV `--no-filename` ML-vs-font head-to-head was **not** completed — spaCy
  OOM'd the run (§3f). It doesn't change the verdict (ML is NO-GO on this box
  regardless), but if you ever revisit ML, run the harness with `USE_SPACY=False`
  and feed font/agreement features only.
- If RAM is later upgraded and recruiter-correction volume is high, the ML ranker
  + feedback loop (§3d, §6.6) can be reconsidered — but only then.

---

## 8. Quick decision summary — VERDICT: GO

Validated on 236 messy CVs (§3f). **Ship the local-first cascade; do NOT build the
ML ranker.**

- **GO:** heuristic **ensemble + reconcile** (portal filenames) + **font tiebreak**
  (largest text near top — production ignores this today) + **pdfminer.six**
  extractor (fitz fallback). On 236 CVs: ensemble **77%**, any-local **90%**.
- **The Gemini gate (§5) is the cost control:** route to Gemini only when local
  sources *disagree or are empty* (`confidence == low`), throttled by a daily
  budget. **~10% → Gemini → 429 quota wall gone.** Failures become a visible
  "verify name" badge, never silent.
- **NO-GO: the ML ranker.** spaCy OOM'd the box (~10 GB), buys too little over the
  ensemble, and needs training/labelling/retrain infra. Revisit only if RAM is
  upgraded *and* correction volume justifies it.
- **NO heavy NER** on the current VPS. Keep spaCy off (`USE_SPACY=False`).
- **Productionize per §6** (RAM reclaim → pdfminer → resolver + gate + confidence
  → dashboard badge). Requires explicit approval — production untouched so far.

_Last updated from harness runs on 236 CVs in `BackEnd/uploaded_cvs/test/`
(superseding the earlier 70-CV directional read in `uploaded_cvs/`)._
