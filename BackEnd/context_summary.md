# Session Context Summary — JobNoc / TalEnd2

A map of everything worked on in this chat. Two buckets:
**(A) shipped to production code**, and **(B) research/decisions kept offline**.
Deep dive on name-parsing R&D lives in `BackEnd/context_parsing.md`.

---

## A. Shipped changes (production code edited)

### A1. CV tagging — tag CVs (incl. ZIP uploads) and edit tags later
**Why:** be able to tag a CV / a whole ZIP of CVs so they're findable.
- `app/api/upload.py`
  - `upload-zip` now accepts a `tags` form field and applies the tag list to
    **every** CV in the ZIP (was hardcoded `[]`).
  - New `PATCH /cv/{cv_id}/tags` — replace tags on an existing CV (auth-scoped).
- `FrontEnd/pages/dashboard.tsx`
  - Tag input shown for ZIP uploads too (note: "applied to all CVs in this ZIP").
  - Inline tag editing in the ledger table (hover ✎ → add/remove → Save/Cancel).

### A2. Search by tag + CSV export
**Why:** filter the database by tag and export contacts.
- `app/api/search.py`
  - New `GET /tags` — distinct list of all tags.
  - Tag filter **case bug fixed**: `$all` was lowercasing tags but they're stored
    as-typed → never matched. Removed the `.lower()`.
- `FrontEnd/pages/search.tsx`
  - Multi-select **tag dropdown** filter (with selected-pills, click-outside close).
  - **Download CSV** button (Name, Email, Phone) for current results.

### A3. Tag-only search (no keyword required)
**Why:** select a tag and see all its CVs without typing a query.
- `app/api/search.py` — `query` made optional; when empty, skip Gemini
  translation + keyword matching and sort by `upload_time` (newest first).
- `FrontEnd/pages/search.tsx` — removed `required`; submit allowed with tags only.

### A4. Parsing-reliability fixes (CVs stuck "uploaded" / "name pending")
**Why:** CVs weren't completing; Celery couldn't reach Redis (`redis7:6380`).
- `app/api/upload.py`
  - `upload_cv` now stores **all** parsed fields and marks `completed`
    immediately (Celery call is best-effort, wrapped in try/except).
  - `upload_zip` parses via FastAPI **BackgroundTasks** (no Redis dependency),
    through `_parse_queue` which processes **5 CVs at a time** (threads) with a
    **15s gap between batches** (to respect Gemini per-minute limits).
  - New `POST /reparse-stuck` — re-parses CVs stuck in `uploaded` or `completed`
    with an empty name. Dashboard has a "Re-parse pending CVs" button.
- `app/utils/parser.py` — fixed `Total_Experience` key mismatch (experience was
  always None). `None.strip()` crash on missing name fixed in `upload_cv`.

### A5. Sentry logging across the pipeline
**Why:** make parsing failures visible (esp. Gemini quota).
- `app/utils/gemini_parser.py` — distinct events: **429 quota** (`gemini_error:
  quota_exceeded`), other HTTP errors, parse failures; `_empty_gemini_result()` helper.
- `app/utils/parser.py` — warning when name comes back empty (with text preview).
- `app/api/upload.py` — `capture_exception` in `_parse_and_store_cv`, `upload_cv`,
  `upload_zip`; **also fixed a bug** where a bare `except Exception` swallowed
  legitimate `HTTPException`s (400s) and re-wrapped them as 500s.
- A `NameError` (leftover `extract_name_with_gemini` call after its import was
  removed) had been crashing every upload with 500 — **fixed**.

---

## B. Investigations & decisions (no code shipped)

### B1. The Gemini quota wall
- Confirmed via Sentry: **HTTP 429** on `/upload-cv` = **daily quota** exhausted
  (resets midnight PT), not just per-minute. A single upload fails when daily cap
  is blown.
- Noted: the **production API key differs from the repo `.env` key** (Sentry showed
  `...gmmP-g`, `.env` has `...2lcg0`) — edit the deployed `.env`, not just local.
- Quick unblocks discussed: wait for reset, swap `GEMINI_MODEL` (separate quota
  bucket — but verify the model id exists; `gemini-3.0-flash` may be invalid),
  second API key. **`.env` changes require an app restart.**

### B2. 500-errors incident
- Both `/upload-cv` and `/list-cvs` 500ing pointed to app-startup failure, not
  logic. Backend runs **directly on the host (cPanel/Passenger), not Docker**
  (only `jobnoc-redis7` + `jobnoc-mongo8` are containers) — so `docker restart`
  doesn't restart the app. Flagged import-time landmine: `mongodb.py` runs
  `ensure_indexes()` at import with no error handling → if Mongo is briefly
  unreachable on boot, the whole app fails to start.

### B3. ML / model approach for names — discussed, then measured (see §C)
- Heavy NER (IndicNER/transformer ~500MB) ruled out: VPS is ~2.7GB and **already
  swapping** (`free -h`: ~950MB available, swap 2.4/2.7GB used); a **job portal is
  also being built on the same box**. RAM can grow later.
- How vendors (Greenhouse/Naukri/RChilli/Affinda) do it: layout/font analysis +
  gazetteers + rules, LLM as a minor layer — not per-CV public-API calls.

---

## C. Name-parsing R&D (offline harness — production untouched)

Full detail + numbers: **`BackEnd/context_parsing.md`**. Tooling:
**`BackEnd/qc_name_eval.py`** (standalone; `autolabel` / `eval` / `train` /
`compare` modes). Measured on 70 real CVs.

Headline results:
- **PDF extractor is the biggest lever:** `fitz` (production) 61% vs
  **`pdfminer.six` 87%** on content `topline`.
- **Font size is the dominant, unused signal:** "pick largest text" = **87%** on
  no-filename CVs (vs 77% for text heuristics). ML + font = **93%** (ceiling 94%).
- **`reconcile`** (filename camelCase split ⇄ email token confirmation) fixes
  jammed portal exports (`DeepakPandeyPMP` → Deepak Pandey).
- `email`/`spacy_ner` are *negative* signals. ~6% genuinely need Gemini/manual.

**Recommended cascade (not yet built):**
`filename/reconcile → font + topline + ML ranker → Gemini fallback (~6%)`.
Two levels: font-only heuristic (87%, no ML) or ML+font (93%, needs training +
feedback loop). Either way Gemini becomes a rare fallback → quota wall solved.

---

## Key preferences & decisions captured
- **Do not touch production code for the name-parsing R&D** — keep it in the
  harness until explicitly chosen (stated repeatedly).
- **No heavy NER** on the current VPS.
- Tooling must be **standalone/portable** (re-implements, doesn't import `app/`).
- All CVs were deleted from Mongo mid-session (`db.cvs.deleteMany({})` via
  `docker exec -it jobnoc-mongo8 mongosh ...`); files in `uploaded_cvs/` are
  cleaned separately.

## Open / next steps
1. Decide build level for names (font-only vs ML+font) — gather ~150–300 CVs
   **stratified toward messy/old/scanned** ones first (current 70 are mostly
   clean portal exports → Mode-A numbers are circular).
2. When productionizing (needs approval): drop dead names CSV at
   `app/utils/parser.py:21-23`; switch extractor to pdfminer; add name-resolver
   cascade + `name_confidence`; optional correction feedback loop.
3. Verify the deployed `.env` Gemini key/model and harden `ensure_indexes()`
   against startup-time Mongo unavailability.

---
_Companion docs: `context_parsing.md` (name-parsing deep dive)._
