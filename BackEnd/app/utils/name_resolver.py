"""Local-first CV name resolution (no Gemini, no spaCy).

Ported from the validated QC harness (`qc_name_eval.py`). On 236 real, messy
Indian CVs this resolves ~90% of names with zero API calls; the residual is
flagged ``low`` confidence so the caller can fall back to Gemini.

The gate is **cross-source agreement** (§5 of context_parsing.md), not any single
method's self-reported certainty:

    high   - >=2 independent sources agree (filename/reconcile, topline, font, email)
    medium - one strong candidate (reconcile/filename/topline/font), nothing agrees
    low    - nothing parseable, or only a weak (email-only) candidate

Only ``low`` should trigger a Gemini call. ``confidence`` and ``source`` are
returned so they can be stored and surfaced (e.g. a "verify name" dashboard badge).

Footprint is tiny: regex + optional indian-namematch + a single PyMuPDF
``get_text("dict")`` on page 1 for the font signal. No transformer/NER models.
"""

import os
import re
from functools import lru_cache

# ---------------------------------------------------------------------------
# indian-namematch: phonetic / spelling-variant matching for Indian names.
# Degrades gracefully (exact + token-set fallback) if the package is missing.
# ---------------------------------------------------------------------------
try:
    from indian_namematch import fuzzymatch

    @lru_cache(maxsize=200000)
    def _inm_match(a, b):
        try:
            return str(fuzzymatch.single_compare(a, b)).strip().lower() == "match"
        except Exception:
            return False
except Exception:  # pragma: no cover - package always present in requirements
    def _inm_match(a, b):
        return False


_TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "shri", "smt", "kum", "er"}

_FILENAME_NOISE = {
    "resume", "cv", "curriculum", "vitae", "profile", "final", "updated",
    "new", "latest", "copy", "doc", "document", "not",
    # job-portal prefixes
    "naukri", "linkedin", "iimjobs", "monster", "shine", "indeed", "foundit",
    "hirist", "instahyre", "cutshort", "updazz", "timesjobs",
}

_CERTS = {"pmp", "cfa", "mba", "ca", "cpa", "phd", "pgdm", "be", "btech",
          "mtech", "msc", "bsc", "pg", "ug", "pmi", "csm", "scrum"}

_HEADER_WORDS = {"resume", "curriculum", "vitae", "cv", "profile", "name", "contact"}

# Words that mean a candidate is a section heading / label, never a person's name.
# A candidate containing ANY of these is rejected (so the topline/font picks fall
# through to the next line, and headers don't get stored as names).
_NON_NAME_WORDS = _HEADER_WORDS | {
    "address", "permanent", "present", "current", "summary", "objective",
    "professional", "experience", "education", "skills", "skill", "core",
    "competency", "competencies", "projects", "project", "work", "academic",
    "achievements", "certifications", "certification", "organization",
    "organisation", "company", "designation", "the", "details", "personal",
    "career", "key", "strengths", "expertise", "qualification", "qualifications",
    "languages", "interests", "hobbies", "references", "declaration", "about",
    # common CV section / skill / domain headings that read like 2-word names
    "management", "development", "stakeholder", "strategy", "analysis",
    "operations", "analytics", "marketing", "sales", "finance", "banking",
    "consulting", "technology", "technologies", "engineering", "leadership",
    "communication", "relationship", "business", "planning", "recruitment",
    "transformation", "governance", "compliance", "delivery", "solutions",
    "services",
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def looks_like_name(name):
    """Reject section headings / labels masquerading as names."""
    nn = normalize(name)
    if not nn:
        return False
    toks = nn.split()
    if not (1 <= len(toks) <= 4):
        return False
    return not any(t in _NON_NAME_WORDS for t in toks)


def normalize(name):
    if not name:
        return ""
    name = re.sub(r"[^A-Za-z\s]", " ", name)
    tokens = [t for t in name.lower().split() if t and t not in _TITLES]
    return " ".join(tokens).strip()


def is_match(a, b):
    """True if two predicted names refer to the same person (any tier)."""
    if not a or not b:
        return False
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if sorted(na.split()) == sorted(nb.split()):     # order-insensitive
        return True
    return _inm_match(a, b)                           # phonetic / Indian variants


def _camel(tok):
    return re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[A-Z]+|[a-z]+", tok)


def _clean(name):
    if not name:
        return None
    toks = [t for t in name.split() if t.strip(".")]
    # Strip leading title / certification prefixes (Mr, Dr, CA, CFA, MBA, ...).
    while len(toks) > 1 and toks[0].lower().strip(".") in (_TITLES | _CERTS):
        toks.pop(0)
    toks = [t.strip(".").capitalize() for t in toks]
    return " ".join(toks) or None


# ---------------------------------------------------------------------------
# Filename: detect generic/UUID names (ZIP uploads) and parse real ones.
# ---------------------------------------------------------------------------
_HEX32 = re.compile(r"^[0-9a-f]{32}", re.IGNORECASE)


def is_generic_filename(filename):
    """True when the filename carries no usable name (UUID/temp/ZIP export)."""
    if not filename:
        return True
    base = os.path.splitext(os.path.basename(filename))[0]
    if base.lower().startswith("temp_") or _HEX32.match(base):
        return True
    cleaned = re.sub(r"[_\-\.]+", " ", re.sub(r"\d+", " ", base))
    alpha = [t for t in cleaned.split() if t.isalpha() and t.lower() not in _FILENAME_NOISE]
    return len(alpha) == 0


def m_filename(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    base = re.sub(r"[_\-\.]+", " ", base)
    base = re.sub(r"\d+", " ", base)
    tokens = [t for t in base.split() if t.lower() not in _FILENAME_NOISE and len(t) > 1]
    tokens = [t for t in tokens if t.isalpha()]
    if 1 <= len(tokens) <= 4:
        return " ".join(w.capitalize() for w in tokens)
    return None


def _fname_name_tokens(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    base = re.split(r"[\[\(]", base)[0]                  # drop [14y_0m] etc.
    base = re.sub(r"[_\-\.]+", " ", base).strip()
    toks = [t for t in base.split() if t.lower() not in _FILENAME_NOISE]
    out = []
    for t in toks:
        out += _camel(t)
    return [t for t in out if t.isalpha()]


def _email_name_tokens(text):
    m = _EMAIL_RE.search(text)
    if not m:
        return []
    local = m.group(0).split("@")[0]
    out = []
    for p in re.split(r"[._\-0-9]+", local):
        out += _camel(p)
    return [p.lower() for p in out if p.isalpha() and len(p) > 1]


def m_reconcile(text, filename):
    """Recover the name from the filename, using email tokens to confirm/segment.

    Handles camelCase-jammed and ALL-CAPS portal exports (DeepakPandeyPMP,
    ANIKETBISWAS) and drops cert/noise tokens the email doesn't confirm.
    """
    ftoks = _fname_name_tokens(filename)
    if not ftoks:
        return None
    etoks = set(_email_name_tokens(text))
    seg = []
    for t in ftoks:
        tl = t.lower()
        if t.isupper() and len(t) > 6 and tl not in etoks:
            rem, parts = tl, []
            for e in sorted(etoks, key=len, reverse=True):
                if rem.startswith(e):
                    parts.append(e)
                    rem = rem[len(e):]
            if not rem and parts:
                seg += parts
                continue
        seg.append(tl)
    keep = [t for t in seg if t not in _CERTS or t in etoks]
    final = [t.capitalize() for t in keep if t.isalpha()]
    return " ".join(final) if final else None


def m_email(text):
    m = _EMAIL_RE.search(text)
    if not m:
        return None
    local = m.group(0).split("@")[0]
    parts = [p for p in re.split(r"[._\-0-9]+", local) if p.isalpha() and len(p) > 1]
    if 1 <= len(parts) <= 3:
        return " ".join(p.capitalize() for p in parts)
    return None


def m_topline(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:12]:
        low = ln.lower()
        if "@" in ln or "http" in low or re.search(r"\d", ln):
            continue
        tokens = ln.split()
        if 2 <= len(tokens) <= 4 and all(re.fullmatch(r"[A-Za-z.]+", t) for t in tokens):
            cand = " ".join(t.capitalize().rstrip(".") for t in tokens)
            if looks_like_name(cand):
                return cand
    return None


# ---------------------------------------------------------------------------
# Font signal: the name is usually the largest text near the top of page 1.
# PyMuPDF only, PDF only; returns (None) candidate + a relative-size lookup.
# ---------------------------------------------------------------------------
def _font_spans(file_path):
    """Page-1 spans -> (list of (raw, normalized, size, y_top), page_height)."""
    if not file_path or not file_path.lower().endswith(".pdf"):
        return [], 0.0
    try:
        import fitz
    except Exception:
        return [], 0.0
    spans = []
    try:
        d = fitz.open(file_path)
        page = d[0]
        page_h = page.rect.height or 1.0
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for s in line.get("spans", []):
                    raw = (s.get("text") or "").strip()
                    nn = normalize(raw)
                    if nn:
                        bbox = s.get("bbox", [0, 0, 0, 0])
                        spans.append((raw, nn, float(s.get("size", 0)), float(bbox[1])))
        d.close()
        return spans, page_h
    except Exception:
        return [], 0.0


def _font_candidate(spans, page_h):
    """Largest-font line in the top of page 1 that looks like a name."""
    best = None
    for raw, nn, size, y in spans:
        toks = raw.split()
        y_rel = (y / page_h) if page_h else 0.5
        if y_rel > 0.5:                       # only the top half
            continue
        if not (2 <= len(toks) <= 4):
            continue
        if not all(re.fullmatch(r"[A-Za-z.]+", t) for t in toks):
            continue
        if not looks_like_name(raw):
            continue
        if best is None or size > best[1]:
            best = (raw, size)
    return _clean(best[0]) if best else None


def _font_rel(name, spans):
    """Relative size (vs median span) of the span matching ``name`` (1.0 if none)."""
    if not spans:
        return 1.0
    nn = normalize(name)
    if not nn:
        return 1.0
    sizes = sorted(s for _, _, s, _ in spans)
    med = sizes[len(sizes) // 2] if sizes else 0.0
    best = None
    for _, t, sz, _y in spans:
        if nn in t or t in nn or sorted(nn.split()) == sorted(t.split()):
            if best is None or sz > best:
                best = sz
    if best is None or not med:
        return 1.0
    return best / med


# ---------------------------------------------------------------------------
# The resolver + gate.
# ---------------------------------------------------------------------------
_SOURCE_PRIORITY = {"reconcile": 5, "filename": 4, "font": 3, "topline": 3, "email": 1}

# Sources that can stand alone as a MEDIUM-confidence name. font/email are
# corroboration/tie-break signals only -- never the sole basis for a name.
_NAME_SOURCES = {"reconcile", "filename", "topline"}


def resolve_name(text, filename="", file_path=None):
    """Resolve a candidate name locally.

    Returns ``{"name": str|None, "confidence": "high"|"medium"|"low",
    "source": str|None}``. ``low`` means the caller should fall back to Gemini.
    """
    text = text or ""
    
    # Try looking up user-learned name mapping first
    try:
        from app.utils.learning import get_name_mapping
        em_temp = m_email(text)
        mapped_name = get_name_mapping(filename, em_temp or "")
        if mapped_name:
            return {"name": mapped_name, "confidence": "high", "source": "user_learning"}
    except Exception:
        pass

    spans, page_h = _font_spans(file_path)

    cands = []  # {name, source}
    generic = is_generic_filename(filename)
    if not generic:
        rec = m_reconcile(text, filename)
        if rec:
            cands.append({"name": rec, "source": "reconcile"})
        fn = m_filename(filename)
        if fn:
            cands.append({"name": fn, "source": "filename"})
    tl = m_topline(text)
    if tl:
        cands.append({"name": tl, "source": "topline"})
    fc = _font_candidate(spans, page_h)
    if fc:
        cands.append({"name": fc, "source": "font"})
    em = m_email(text)
    if em:
        cands.append({"name": em, "source": "email"})

    # Drop any candidate that is actually a section heading / label.
    cands = [c for c in cands if looks_like_name(c["name"])]

    # Deduplicate by normalized name, keeping the highest-priority source.
    uniq = {}
    for c in cands:
        key = normalize(c["name"])
        if not key:
            continue
        cur = uniq.get(key)
        if cur is None or _SOURCE_PRIORITY.get(c["source"], 0) > _SOURCE_PRIORITY.get(cur["source"], 0):
            uniq[key] = c
    cands = list(uniq.values())

    if not cands:
        return {"name": None, "confidence": "low", "source": None}

    for c in cands:
        c["agree"] = sum(1 for o in cands if o is not c and is_match(c["name"], o["name"]))
        c["font_rel"] = _font_rel(c["name"], spans)
        c["prio"] = _SOURCE_PRIORITY.get(c["source"], 0)

    # HIGH: >=2 independent sources agree.
    agreed = [c for c in cands if c["agree"] >= 1]
    if agreed:
        best = max(agreed, key=lambda c: (c["agree"], c["font_rel"], c["prio"]))
        return {"name": _clean(best["name"]), "confidence": "high", "source": best["source"]}

    # MEDIUM: one uncorroborated name-derivation. font/email cannot stand alone
    # (the largest text on a page is often a company/title/degree, and an email
    # local-part is a weak guess) -> those fall through to Gemini instead.
    strong = [c for c in cands if c["source"] in _NAME_SOURCES]
    if strong:
        best = max(strong, key=lambda c: (c["font_rel"], c["prio"]))
        return {"name": _clean(best["name"]), "confidence": "medium", "source": best["source"]}

    # LOW: nothing trustworthy locally (only a font-blob/email guess) -> Gemini.
    return {"name": None, "confidence": "low", "source": None}
