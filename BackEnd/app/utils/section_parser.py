"""Local-first section-based extraction of the non-name CV fields.

Ported from the validated QC harness (`qc_fields_eval.py`). Segments the CV by
header keywords (the one RAM-free idea from asimokby/cv-parser-huggingface — its
transformer stack would OOM the VPS) and extracts the CURRENT company, designation
and total experience positionally, each with a confidence tier.

On 126 hand-labeled real CVs the ``high`` tier is 87-90% precise per field; the
caller accepts ``high`` and routes ``medium``/empty to Gemini (per-field gate).

Footprint is tiny: regex + a job-titles gazetteer (titles_combined.txt). No
transformers / NER / spaCy. Skills + education stay on the existing parser path.
"""

import datetime
import os
import re

THIS_YEAR = datetime.date.today().year
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TITLES_PATH = os.path.join(BASE_DIR, "../../titles_combined.txt")


# --------------------------------------------------------------------------- #
# Job-titles gazetteer (degrades gracefully if the file is missing)
# --------------------------------------------------------------------------- #
def _load_titles(path):
    try:
        with open(path, encoding="utf-8") as f:
            return {ln.strip().lower() for ln in f if ln.strip()}
    except Exception:
        return set()


TITLES = _load_titles(_TITLES_PATH)
_TITLE_MAXW = max((len(t.split()) for t in TITLES), default=6)

_GENERIC_DOMAINS = {
    "gmail", "yahoo", "outlook", "hotmail", "rediffmail", "rediff", "icloud",
    "live", "ymail", "protonmail", "aol", "msn", "googlemail", "yopmail",
}
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# --------------------------------------------------------------------------- #
# Section segmentation (header-keyword based)
# --------------------------------------------------------------------------- #
_SECTION_KEYS = {
    "experience": ["work experience", "professional experience", "employment",
                   "work history", "experience", "career", "professional summary"],
    "education": ["education", "academic", "qualification", "educational"],
    "skills": ["skills", "technical skills", "core competencies", "competencies",
               "areas of expertise", "key skills", "technical proficiencies"],
    "summary": ["summary", "objective", "profile", "about"],
    "projects": ["projects", "project"],
    "certifications": ["certifications", "certification", "courses"],
}


def _is_header(line):
    s = line.strip()
    if not s or len(s) > 40 or re.search(r"\d", s):
        return None
    low = re.sub(r"[^a-z ]", "", s.lower()).strip()
    if not low:
        return None
    for sec, keys in _SECTION_KEYS.items():
        for k in keys:
            if low == k or low.startswith(k):
                if s.isupper() or s.istitle() or len(s.split()) <= 4:
                    return sec
    return None


def segment(text):
    """Return dict section -> text block. Lines before the first header = 'head'."""
    lines = text.splitlines()
    sections, cur, buf = {}, "head", []
    for ln in lines:
        sec = _is_header(ln)
        if sec:
            sections.setdefault(cur, []).extend(buf)
            buf, cur = [], sec
        else:
            buf.append(ln)
    sections.setdefault(cur, []).extend(buf)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _ngrams(tokens, n):
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


# --------------------------------------------------------------------------- #
# Date-range parsing (the reliable anchor for a job block)
# --------------------------------------------------------------------------- #
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")
_MON_IDX = {m: i + 1 for i, m in enumerate(_MONTHS)}
_MON_RE = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{_MON_RE}[\s\-/,.]*)?(?:\d{{1,2}}[\s\-/.]+){{0,2}}(?:19|20)\d{{2}}"
_PRESENT = r"present|current|till\s*date|till\s*now|to\s*date|ongoing|now|date|continue"
_RANGE_RE = re.compile(
    rf"({_DATE})\s*(?:[-–—]+|\bto\b)\s*({_DATE}|{_PRESENT})", re.I)
_PRESENT_RE = re.compile(_PRESENT, re.I)


def _year_of(tok):
    if not tok:
        return None
    if _PRESENT_RE.search(tok):
        return THIS_YEAR + (datetime.date.today().month - 1) / 12.0
    ym = re.search(r"(?:19|20)\d{2}", tok)
    if not ym:
        return None
    year = int(ym.group(0))
    mon = 0
    mm = re.search(_MON_RE, tok, re.I)
    if mm:
        mon = _MON_IDX.get(mm.group(0)[:3].lower(), 0)
    return year + (mon - 1) / 12.0 if mon else float(year)


def find_date_ranges(text):
    out = []
    for m in _RANGE_RE.finditer(text):
        s, e = _year_of(m.group(1)), _year_of(m.group(2))
        if s is None or e is None:
            continue
        if 1980 <= s <= THIS_YEAR + 1 and e >= s - 0.1:
            out.append((s, e, m.start()))
    return out


# --------------------------------------------------------------------------- #
# Company / designation positional helpers
# --------------------------------------------------------------------------- #
_COMPANY_SUFFIX = re.compile(
    r"\b(pvt\.?\s*ltd|private\s+limited|ltd\.?|llp|inc\.?|llc|technologies|"
    r"technology|solutions|services|systems|consulting|consultancy|limited|"
    r"corporation|corp\.?|industries|enterprises|infotech|software|labs|"
    r"networks|ventures|bank|university|institute)\b", re.I)
_LOC_TAIL = re.compile(r"\s*[,|(].*$")

_NON_COMPANY = {
    "responsibilities", "responsibility", "achievements", "accomplishments",
    "summary", "objective", "profile", "projects", "project", "skills",
    "education", "experience", "roles", "duties", "highlights", "details",
    "description", "overview", "responsibilities:", "competencies",
}

_TITLE_WORDS = {
    "manager", "intern", "engineer", "analyst", "lead", "developer", "consultant",
    "executive", "officer", "director", "specialist", "associate", "coordinator",
    "head", "president", "vp", "architect", "designer", "administrator", "trainee",
    "scientist", "advisor", "adviser", "supervisor", "technician", "representative",
    "accountant", "recruiter", "professional", "strategist", "founder", "partner",
    "consulting",
}

_NOT_DESIGNATION = {
    "chartered accountant", "company secretary", "cost accountant",
    "mechanical engineer", "civil engineer", "electrical engineer",
    "automobile engineer", "long term", "change management",
}
# Naukri/portal filename total-experience tag, e.g. "Name[14y_0m].pdf"
_FNAME_EXP = re.compile(r"\[(\d{1,2})\s*y(?:[_ ]*(\d{1,2})\s*m)?", re.I)


def _strip_to_company(line):
    s = _RANGE_RE.sub(" ", line)
    s = _LOC_TAIL.sub("", s)
    s = re.sub(r"(?:19|20)\d{2}", " ", s)
    s = _PRESENT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" \t|-–—•·:.")
    s = re.sub(r"\s*[)\]]+\s*$", "", s)
    s = re.sub(r"^[(\[]\s*", "", s)
    return s


def _is_company_like(s):
    if not s or len(s) < 3:
        return False
    words = s.split()
    if not (1 <= len(words) <= 8):
        return False
    if not any(w[:1].isupper() for w in words):
        return False
    if any(w.lower().strip(":") in _NON_COMPANY for w in words):
        return False
    return True


def _company_from_suffix_line(line):
    """Company = the phrase ENDING at the LAST legal suffix, so a title jammed onto
    the line or a trailing parenthetical alias doesn't displace the real name."""
    s = re.sub(r"\([^)]*\)", " ", line)
    s = _RANGE_RE.sub("|", s)
    s = re.sub(r"(?:19|20)\d{2}", "|", s)
    s = _PRESENT_RE.sub("|", s)
    matches = list(_COMPANY_SUFFIX.finditer(s))
    if not matches:
        return None
    m = matches[-1]
    tail_words = [w for w in re.findall(r"[A-Za-z]+", s[m.end():]) if len(w) > 1]
    if len(tail_words) > 1:                          # suffix is mid-prose -> skip
        return None
    head = s[:m.end()]
    seg = re.split(r"\||\s[-–—]\s", head)[-1]
    cand = seg.strip(" .-&|\t")
    w = cand.split()
    if len(w) > 6:
        cand = " ".join(w[-5:])
    return cand if _is_company_like(cand) else None


def _has_title_word(line):
    toks = re.findall(r"[a-z]+", line.lower())
    return any(t in _TITLE_WORDS for t in toks)


def _at_company(line):
    m = re.search(r"\bat\s+([A-Z][A-Za-z0-9&.,'\- ]{2,50})", line)
    if not m:
        return None
    cand = _strip_to_company(m.group(1))
    return cand if _is_company_like(cand) else None


def _title_in_line(line):
    """Longest titles gazetteer hit in a single line, or None."""
    if not TITLES:
        return None
    low = re.sub(r"[^a-z &/]", " ", line.lower())
    toks = low.split()
    best = None
    
    # Merge custom user-verified titles dynamically
    try:
        from app.utils.learning import get_custom_titles
        custom = get_custom_titles()
        all_titles = TITLES | custom
        title_maxw = max(_TITLE_MAXW, max((len(t.split()) for t in custom), default=6))
    except Exception:
        all_titles = TITLES
        title_maxw = _TITLE_MAXW

    for n in range(min(title_maxw, len(toks)), 1, -1):
        hit = next((g for g in _ngrams(toks, n) if g in all_titles), None)
        if hit and (best is None or len(hit) > len(best)):
            best = hit
    return best


def _refine_designation(line, gaz_hit):
    """Prefer the full title LINE over the gazetteer fragment, without dragging in
    company/product context (dash within title kept; product tail dropped)."""
    s = _RANGE_RE.sub(" ", line)
    s = re.sub(r"[–—�]", "-", s)
    s = re.sub(r"\s+", " ", s).strip(" \t|-•·:*▪◦")
    s = re.split(r"\s*[(|]", s)[0].strip()
    parts = re.split(r"\s+-\s+", s, maxsplit=1)
    if len(parts) == 2:
        left, right = parts
        if not (_has_title_word(right) or _title_in_line(right)):
            s = left.strip()
    s = s.strip(" \t|-•·:*").strip()
    if not s or len(s.split()) > 8 or gaz_hit.lower() not in s.lower():
        return gaz_hit.title()
    return s.title()


def _extract_company_designation(secs, full, emails):
    """Positional extraction of the CURRENT company + designation, anchored on the
    first work-block date range. Returns (company, c_conf, designation, d_conf)."""
    exp = secs.get("experience", "")
    lines = [l.strip() for l in exp.splitlines() if l.strip()]
    region = lines[:25]
    company = c_conf = desig = d_conf = None

    # Check experience section for dynamically learned/verified companies first
    try:
        from app.utils.learning import get_known_companies
        known_cos = get_known_companies()
        if known_cos:
            for l in region:
                for co in known_cos:
                    if re.search(rf"\b{re.escape(co)}\b", l, re.I):
                        company = co
                        c_conf = "high"
                        break
                if company:
                    break
    except Exception:
        pass

    for l in region:                                  # 1) explicit labels (strongest)
        if not desig:
            m = re.search(r"designation\s*[:\-]\s*(.+)", l, re.I)
            if m:
                cand = re.split(r"\s[|(]|\s[-–]\s", m.group(1))[0]
                cand = _RANGE_RE.sub("", cand).strip(" :-")
                if cand:
                    desig, d_conf = cand.title(), "high"
        if not company:
            m = re.search(r"\bcompany\s*[:\-]\s*(.+)", l, re.I)
            if m:
                cand = _strip_to_company(m.group(1))
                if _is_company_like(cand):
                    company, c_conf = cand, "high"

    anchor = next((i for i, l in enumerate(region) if _RANGE_RE.search(l)), None)
    if anchor is not None:
        window = region[max(0, anchor - 2):anchor + 3]
        if not company:
            for l in window:                          # a) "Title at Company (dates)"
                cand = _at_company(l)
                if cand:
                    company, c_conf = cand, "high"
                    break
        if not company:
            for l in window:                          # b) explicit company-suffix line
                if _COMPANY_SUFFIX.search(l) and not _at_company(l):
                    cand = _company_from_suffix_line(l) or _strip_to_company(l)
                    if cand and _is_company_like(cand):
                        company, c_conf = cand, "high"
                        break
        if not company and (_title_in_line(region[anchor])
                            or _has_title_word(region[anchor])):
            for l in region[anchor + 1:anchor + 3]:   # b2) title-first: company next line
                if re.match(r"^[•\-*·�▪◦o]\s", l) or _RANGE_RE.search(l):
                    continue
                cand = _strip_to_company(l)
                if (_is_company_like(cand) and len(cand.split()) <= 5
                        and not _title_in_line(l) and not _has_title_word(l)):
                    company, c_conf = cand, "medium"
                    break
        if not company:                               # c) the date line itself
            cand = _strip_to_company(region[anchor])
            if (_is_company_like(cand) and not _title_in_line(region[anchor])
                    and not _has_title_word(region[anchor])):
                company, c_conf = cand, "medium"
        if not desig:
            for l in window:
                hit = _title_in_line(l)
                if hit:
                    desig, d_conf = _refine_designation(l, hit), "high"
                    break

    if not company:                                   # fallback: work-email domain
        for em in emails:
            dom = em.split("@")[-1].split(".")[0].lower()
            if dom and dom not in _GENERIC_DOMAINS and len(dom) > 2:
                company, c_conf = dom.title(), "medium"
                break
    if not desig:                                     # fallback: gazetteer over top
        region2 = "\n".join([secs.get("head", "")] + full.splitlines()[:15])
        hit = None
        for l in region2.splitlines():
            h = _title_in_line(l)
            if h and (hit is None or len(h) > len(hit)):
                hit = h
        if hit:
            desig, d_conf = hit.title(), "medium"

    if desig and " ".join(re.sub(r"[^a-z ]", " ", desig.lower()).split()) in _NOT_DESIGNATION:
        desig, d_conf = None, None                    # degrees are never a designation

    return company, c_conf, desig, d_conf


def _extract_experience(secs, full, filename=""):
    """Total experience (years) + confidence. Priority: portal [Ny_Mm] filename tag
    > explicit 'N years' near 'experience' > span across work-section date ranges."""
    fm = _FNAME_EXP.search(filename or "")
    if fm:
        yrs = int(fm.group(1)) + (int(fm.group(2)) / 12.0 if fm.group(2) else 0)
        return round(yrs, 1), "high"

    near = re.search(
        r"experience[^\n]{0,40}?(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs)"
        r"|(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs)[^\n]{0,20}?experience",
        full, re.I)
    if near:
        return float(next(g for g in near.groups() if g)), "high"

    ranges = find_date_ranges(secs.get("experience", "") or full)
    if ranges:
        # Span = earliest start -> latest end. This is only a WEAK proxy for total
        # professional experience: internships that overlap study years (or any old
        # date in the section) inflate it (e.g. a fresher with a 2020 internship
        # reads as 6 yrs). So it's "medium" -> routed to Gemini, never trusted as-is.
        span = max(e for _, e, _ in ranges) - min(s for s, _, _ in ranges)
        if 0 < span <= 45:
            return round(span, 1), "medium"

    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs)\b", full, re.I)
    if m:
        return float(m.group(1)), "medium"
    return None, None


def _tidy(s):
    """Collapse whitespace and strip leading/trailing punctuation for storage."""
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip(" \t/|\\-–—•·:.,&")
    return s or None


# Cap stored section text so the CV doc doesn't balloon (raw_text is already stored).
_SECTION_CAP = 3000


def resolve_fields(text, filename=""):
    """Local section-based extraction of the non-name fields.

    Returns ``company``/``designation``/``experience`` each with a ``*_confidence``
    of ``high``|``medium``|``None`` (``high`` = trust locally; otherwise the caller
    falls back to Gemini), plus the segmented ``sections``.
    """
    text = text or ""
    secs = segment(text)
    emails = _EMAIL_RE.findall(text)
    company, c_conf, desig, d_conf = _extract_company_designation(secs, text, emails)
    exp, e_conf = _extract_experience(secs, text, filename)
    sections = {k: v[:_SECTION_CAP] for k, v in secs.items() if k != "head" and v}
    return {
        "company": _tidy(company),
        "company_confidence": c_conf,
        "designation": _tidy(desig),
        "designation_confidence": d_conf,
        "experience": exp,
        "experience_confidence": e_conf,
        "sections": sections,
    }
