"""Standalone QC harness for the NON-name CV fields:
    company | designation | total_experience | skills

Self-contained: imports nothing from app/. Tests whether these four fields can be
recovered LOCALLY (gazetteer + regex + header-based section segmentation) so that
"skip Gemini on confident names" doesn't blank them out.

Approach (no transformers, no spaCy):
  1. Split the CV into sections by header keywords (Work / Education / Skills...).
  2. skills      -> tokenize the Skills section, set-intersect LINKEDIN_SKILLS_ORIGINAL.
  3. designation -> longest job-title (titles_combined.txt) near the top / work header.
  4. experience  -> "N years" regex near 'experience', else date-range math.
  5. company     -> work-email domain, else "at/| <Company>" near top / first job.

There are NO ground-truth labels for these fields, so this reports COVERAGE
(how often each field is found) plus a sample for eyeballing -- not accuracy.

USAGE:
    python qc_fields_eval.py --dir uploaded_cvs/test --limit 40
    python qc_fields_eval.py --dir uploaded_cvs/test --engine fitz --show 25
"""

import argparse
import csv
import datetime
import os
import re

THIS_YEAR = datetime.date.today().year
BASE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# Gazetteers
# --------------------------------------------------------------------------- #
def _load_lines(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception as e:
        print(f"  [warn] cannot load {path}: {e}")
        return []


_SKILL_STOP = {
    "c", "r", "go", "d", "j", ".com", ".net", ".htaccess", "1-wire", "ai",
    "it", "a", "b", "e", "ml", "ui", "ux", "qa", "pm", "hr",
}
SKILLS = {s.lower() for s in _load_lines(os.path.join(BASE, "LINKEDIN_SKILLS_ORIGINAL.txt"))
          if len(s) >= 3 and s.lower() not in _SKILL_STOP}
TITLES = {t.lower() for t in _load_lines(os.path.join(BASE, "titles_combined.txt"))}
_TITLE_MAXW = max((len(t.split()) for t in TITLES), default=6)

_GENERIC_DOMAINS = {
    "gmail", "yahoo", "outlook", "hotmail", "rediffmail", "rediff", "icloud",
    "live", "ymail", "protonmail", "aol", "msn", "googlemail", "yopmail",
}


# --------------------------------------------------------------------------- #
# Text extraction
# --------------------------------------------------------------------------- #
def extract_text(path, engine="pdfminer"):
    ext = path.lower().rsplit(".", 1)[-1]
    if ext == "docx":
        try:
            import docx
            return "\n".join(p.text for p in docx.Document(path).paragraphs).strip()
        except Exception as e:
            print(f"  [warn] docx {os.path.basename(path)}: {e}")
            return ""
    if ext != "pdf":
        return ""
    order = [engine, "pdfminer", "fitz"]
    for eng in dict.fromkeys(order):
        try:
            if eng == "pdfminer":
                from pdfminer.high_level import extract_text as _pm
                return (_pm(path) or "").strip()
            if eng == "fitz":
                import fitz
                d = fitz.open(path)
                t = "".join((pg.get_text("text") or "") for pg in d)
                d.close()
                return t.strip()
        except ImportError:
            continue
        except Exception as e:
            print(f"  [warn] {eng} {os.path.basename(path)}: {e}")
    return ""


# --------------------------------------------------------------------------- #
# Section segmentation (header-keyword based, the one reusable idea from the HF repo)
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
                # headers are usually short and Title/UPPER case
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


# --------------------------------------------------------------------------- #
# Field extractors
# --------------------------------------------------------------------------- #
def _ngrams(tokens, n):
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


# --------------------------------------------------------------------------- #
# Date-range parsing (the reliable anchor for a job block)
# --------------------------------------------------------------------------- #
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")
_MON_IDX = {m: i + 1 for i, m in enumerate(_MONTHS)}
_MON_RE = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# a single date token: optional month-name, up to two leading day/month numbers,
# then a 4-digit year (handles "Mar 2024", "03/2024", "12-01-2015", "2020").
_DATE = rf"(?:{_MON_RE}[\s\-/,.]*)?(?:\d{{1,2}}[\s\-/.]+){{0,2}}(?:19|20)\d{{2}}"
_PRESENT = r"present|current|till\s*date|till\s*now|to\s*date|ongoing|now|date|continue"
_RANGE_RE = re.compile(
    rf"({_DATE})\s*(?:[-–—]+|\bto\b)\s*({_DATE}|{_PRESENT})", re.I)
_PRESENT_RE = re.compile(_PRESENT, re.I)


def _year_of(tok):
    """Date token -> fractional year (month/12 if a month name is present)."""
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
    """All (start_year, end_year, char_pos) ranges, in document order."""
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
# strip a trailing location / context tail: ", Pune, India" | "(Bangalore)" | "| ..."
_LOC_TAIL = re.compile(r"\s*[,|(].*$")


def _strip_to_company(line):
    """Remove date ranges / years / location tail; return a clean company string."""
    s = _RANGE_RE.sub(" ", line)
    s = _LOC_TAIL.sub("", s)
    s = re.sub(r"(?:19|20)\d{2}", " ", s)
    s = _PRESENT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" \t|-–—•·:.")
    s = re.sub(r"\s*[)\]]+\s*$", "", s)          # stray trailing bracket
    s = re.sub(r"^[(\[]\s*", "", s)
    return s


# section/heading words that are never a company name
_NON_COMPANY = {
    "responsibilities", "responsibility", "achievements", "accomplishments",
    "summary", "objective", "profile", "projects", "project", "skills",
    "education", "experience", "roles", "duties", "highlights", "details",
    "description", "overview", "responsibilities:", "competencies",
}


def _company_from_suffix_line(line):
    """Company = the phrase ENDING at the legal suffix (Pvt Ltd / Technologies / ...),
    so a title jammed onto the same line ('GM - Finance ... IRIS Health Ltd') or a
    trailing parenthetical alias doesn't swallow / displace the real name."""
    s = re.sub(r"\([^)]*\)", " ", line)             # drop balanced parentheticals
    s = _RANGE_RE.sub("|", s)                        # mark date / boundary positions
    s = re.sub(r"(?:19|20)\d{2}", "|", s)
    s = _PRESENT_RE.sub("|", s)
    matches = list(_COMPANY_SUFFIX.finditer(s))
    if not matches:
        return None
    m = matches[-1]                                 # the LAST suffix (e.g. ...Health services *Ltd*)
    # a real company line ends at the suffix (maybe + location); if real words
    # follow, the suffix is mid-prose ('Information Technology & industries') -> skip.
    tail_words = [w for w in re.findall(r"[A-Za-z]+", s[m.end():]) if len(w) > 1]
    if len(tail_words) > 1:
        return None
    head = s[:m.end()]
    seg = re.split(r"\||\s[-–—]\s", head)[-1]        # text after the last boundary
    cand = seg.strip(" .-&|\t")
    w = cand.split()
    if len(w) > 6:                                   # still noisy -> last 5 tokens
        cand = " ".join(w[-5:])
    return cand if _is_company_like(cand) else None


def _is_company_like(s):
    if not s or len(s) < 3:
        return False
    words = s.split()
    if not (1 <= len(words) <= 8):
        return False
    if not any(w[:1].isupper() for w in words):  # need a proper-noun-ish token
        return False
    if any(w.lower().strip(":") in _NON_COMPANY for w in words):
        return False
    return True


# common job-title words — catch designations the 74k gazetteer misses, so they
# don't get stored as a company in the low-confidence date-line fallback.
_TITLE_WORDS = {
    "manager", "intern", "engineer", "analyst", "lead", "developer", "consultant",
    "executive", "officer", "director", "specialist", "associate", "coordinator",
    "head", "president", "vp", "architect", "designer", "administrator", "trainee",
    "scientist", "advisor", "adviser", "supervisor", "technician", "representative",
    "accountant", "recruiter", "professional", "strategist", "founder", "partner",
    "consulting",
}


def _has_title_word(line):
    toks = re.findall(r"[a-z]+", line.lower())
    return any(t in _TITLE_WORDS for t in toks)


def _at_company(line):
    """Company from a 'Title at Company (dates)' line, or None."""
    m = re.search(r"\bat\s+([A-Z][A-Za-z0-9&.,'\- ]{2,50})", line)
    if not m:
        return None
    cand = _strip_to_company(m.group(1))
    return cand if _is_company_like(cand) else None


def _refine_designation(line, gaz_hit):
    """Prefer the full title LINE over the gazetteer fragment, without dragging in
    company/product context.

    'Manager – Human Resources Business Partner' -> kept whole (dash is within the
    title); 'PRODUCT MANAGER - Beephire.ai (B2B)' -> 'Product Manager' (right side
    is a product, not a title). Falls back to the gazetteer hit if the line looks
    too long / noisy."""
    s = _RANGE_RE.sub(" ", line)
    s = re.sub(r"[–—�]", "-", s)                 # normalise dash-likes (incl. mojibake)
    s = re.sub(r"\s+", " ", s).strip(" \t|-•·:*▪◦")
    s = re.split(r"\s*[(|]", s)[0].strip()       # drop "(B2B...)" / "| ..." context
    parts = re.split(r"\s+-\s+", s, maxsplit=1)  # "Title - <tail>"
    if len(parts) == 2:
        left, right = parts
        if not (_has_title_word(right) or _title_in_line(right)):
            s = left.strip()                     # tail is a product/company -> drop it
    s = s.strip(" \t|-•·:*").strip()
    if not s or len(s.split()) > 8 or gaz_hit.lower() not in s.lower():
        return gaz_hit.title()
    return s.title()


def _title_in_line(line):
    """Longest titles_combined.txt gazetteer hit in a single line, or None."""
    low = re.sub(r"[^a-z &/]", " ", line.lower())
    toks = low.split()
    best = None
    for n in range(min(_TITLE_MAXW, len(toks)), 1, -1):
        hit = next((g for g in _ngrams(toks, n) if g in TITLES), None)
        if hit and (best is None or len(hit) > len(best)):
            best = hit
    return best


def extract_skills(secs, full):
    src = secs.get("skills") or full
    text = src.lower()
    toks = re.findall(r"[a-z0-9.+#]+", text)
    found = set()
    for n in (1, 2, 3):
        for g in _ngrams(toks, n):
            if g in SKILLS:
                found.add(g)
    # prefer multi-word skills; drop unigrams that are part of a found bigram
    bigword = {w for s in found if " " in s for w in s.split()}
    found = {s for s in found if " " in s or s not in bigword}
    return sorted(found, key=len, reverse=True)[:25]


def extract_company_designation(secs, full, emails):
    """Positional extraction of the CURRENT company + designation.

    The first job block (reverse-chronological) carries both, anchored on its
    date range. Handles company-first and title-first orderings, explicit
    'Designation:'/'Company:' labels, and company-suffix lines (Pvt Ltd, ...).
    Returns (company, c_conf, designation, d_conf).
    """
    exp = secs.get("experience", "")
    lines = [l.strip() for l in exp.splitlines() if l.strip()]
    region = lines[:25]
    company = c_conf = desig = d_conf = None

    # 1) Explicit labels (strongest) anywhere near the top of the work section.
    for l in region:
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

    # 2) Anchor on the first date range; company/designation live in its window.
    anchor = next((i for i, l in enumerate(region) if _RANGE_RE.search(l)), None)
    if anchor is not None:
        window = region[max(0, anchor - 2):anchor + 3]
        if not company:
            for l in window:                      # a) "Title at Company (dates)"
                cand = _at_company(l)
                if cand:
                    company, c_conf = cand, "high"
                    break
        if not company:
            for l in window:                      # b) explicit company-suffix line
                if _COMPANY_SUFFIX.search(l) and not _at_company(l):
                    # suffix-phrase keys on the reliable legal suffix (handles a
                    # designation jammed before it); fall back to the whole line.
                    cand = _company_from_suffix_line(l) or _strip_to_company(l)
                    if cand and _is_company_like(cand):
                        company, c_conf = cand, "high"
                        break
        if not company and (_title_in_line(region[anchor])
                            or _has_title_word(region[anchor])):
            # b2) title-first layout: company is often the next short line.
            for l in region[anchor + 1:anchor + 3]:
                if re.match(r"^[•\-*·�▪◦o]\s", l) or _RANGE_RE.search(l):
                    continue
                cand = _strip_to_company(l)
                if (_is_company_like(cand) and len(cand.split()) <= 5
                        and not _title_in_line(l) and not _has_title_word(l)):
                    company, c_conf = cand, "medium"
                    break
        if not company:                           # c) the date line itself, stripped
            cand = _strip_to_company(region[anchor])
            # ...but not when that line is really the job TITLE (title-first
            # layouts) — a gazetteer title / title-word is never a company name.
            if (_is_company_like(cand) and not _title_in_line(region[anchor])
                    and not _has_title_word(region[anchor])):
                company, c_conf = cand, "medium"
        if not desig:
            for l in window:
                hit = _title_in_line(l)
                if hit:
                    desig, d_conf = _refine_designation(l, hit), "high"
                    break

    # 3) Fallbacks.
    if not company:                               # work-email domain
        for em in emails:
            dom = em.split("@")[-1].split(".")[0].lower()
            if dom and dom not in _GENERIC_DOMAINS and len(dom) > 2:
                company, c_conf = dom.title(), "medium"
                break
    if not desig:                                 # gazetteer over head + top lines
        region2 = "\n".join([secs.get("head", "")] + full.splitlines()[:15])
        hit = None
        for l in region2.splitlines():
            h = _title_in_line(l)
            if h and (hit is None or len(h) > len(hit)):
                hit = h
        if hit:
            desig, d_conf = hit.title(), "medium"

    # Qualifications / degrees live in the 74k title gazetteer but are never the
    # CURRENT designation -> drop so they fall through to the LLM gate.
    if desig and " ".join(re.sub(r"[^a-z ]", " ", desig.lower()).split()) in _NOT_DESIGNATION:
        desig, d_conf = None, None

    return company, c_conf, desig, d_conf


_NOT_DESIGNATION = {
    "chartered accountant", "company secretary", "cost accountant",
    "mechanical engineer", "civil engineer", "electrical engineer",
    "automobile engineer", "long term", "change management",
}
# Naukri/portal filename total-experience tag, e.g. "Name[14y_0m].pdf"
_FNAME_EXP = re.compile(r"\[(\d{1,2})\s*y(?:[_ ]*(\d{1,2})\s*m)?", re.I)


def extract_experience(secs, full, filename=""):
    """Total experience in years. Priority: portal filename tag [Ny_Mm] (the
    authoritative Naukri value) > explicit 'N years' near 'experience' > span
    across work-section date ranges. Returns (years, confidence)."""
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
        # Span (earliest start -> latest end) is a WEAK proxy for total experience:
        # internships overlapping study years inflate it -> "medium", routed to Gemini.
        span = max(e for _, e, _ in ranges) - min(s for s, _, _ in ranges)
        if 0 < span <= 45:
            return round(span, 1), "medium"

    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs)\b", full, re.I)
    if m:
        return float(m.group(1)), "medium"
    return None, None


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def parse_fields(text, filename=""):
    secs = segment(text)
    emails = _EMAIL_RE.findall(text)
    company, c_conf, desig, d_conf = extract_company_designation(secs, text, emails)
    exp, e_conf = extract_experience(secs, text, filename)
    return {
        "skills": extract_skills(secs, text),
        "designation": desig,
        "designation_conf": d_conf,
        "experience": exp,
        "experience_conf": e_conf,
        "company": company,
        "company_conf": c_conf,
        "sections": sorted(k for k in secs if k != "head"),
    }


# --------------------------------------------------------------------------- #
# Scoring against hand-labeled truth (company/designation/experience)
# --------------------------------------------------------------------------- #
_CO_STOP = {"pvt", "ltd", "limited", "private", "inc", "llp", "llc", "technologies",
            "technology", "solutions", "services", "systems", "consulting", "india",
            "co", "corporation", "corp", "group", "and", "the", "company", "networks",
            "global", "enterprises", "industries"}
_DES_STOP = {"the", "of", "and", "for", "a", "ii", "iii", "sr", "jr"}


def _toks(s, stop):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return [t for t in s.split() if t not in stop and len(t) > 1]


def co_match(pred, truth):
    p, t = _toks(pred, _CO_STOP), _toks(truth, _CO_STOP)
    if not p or not t:
        return False
    sp, st = set(p), set(t)
    if sp & st and len(sp & st) / min(len(sp), len(st)) >= 0.5:
        return True
    return " ".join(p) in " ".join(t) or " ".join(t) in " ".join(p)


def des_match(pred, truth):
    p, t = set(_toks(pred, _DES_STOP)), set(_toks(truth, _DES_STOP))
    if not p or not t:
        return False
    return len(p & t) / min(len(p), len(t)) >= 0.5


def exp_match(pred, truth):
    try:
        return abs(float(pred) - float(truth)) <= 1.5
    except (TypeError, ValueError):
        return False


def run_score(truth_path, cv_dir, engine):
    import csv as _csv
    truth = {}
    with open(truth_path, encoding="utf-8-sig") as f:
        for row in _csv.DictReader(f):
            truth[row["file"].strip()] = row
    by_name = {os.path.basename(p): p for p in find_cvs(cv_dir)}

    matchers = {"company": co_match, "designation": des_match, "experience": exp_match}
    field_pred = {"company": "company", "designation": "designation", "experience": "experience"}
    conf_key = {"company": "company_conf", "designation": "designation_conf",
                "experience": "experience_conf"}
    # stats[field] = {truth_n, pred_n, correct, by_conf{conf:[correct,total]}}
    stats = {k: {"truth_n": 0, "pred_n": 0, "correct": 0, "conf": {}} for k in matchers}
    missing = []
    mism = {k: [] for k in matchers}

    for fname, row in truth.items():
        p = by_name.get(fname)
        if not p:
            missing.append(fname)
            continue
        text = extract_text(p, engine)
        r = parse_fields(text, fname) if text and len(text) >= 50 else {}
        for field, matcher in matchers.items():
            tv = (row.get(field + "_TRUE") or "").strip()
            if tv == "":
                continue
            stats[field]["truth_n"] += 1
            pv = r.get(field_pred[field])
            conf = r.get(conf_key[field]) or "none"
            has_pred = pv not in (None, "", [])
            if has_pred:
                stats[field]["pred_n"] += 1
            ok = has_pred and matcher(str(pv), tv)
            if ok:
                stats[field]["correct"] += 1
            c = stats[field]["conf"].setdefault(conf, [0, 0])
            c[1] += 1
            if ok:
                c[0] += 1
            if has_pred and not ok:
                mism[field].append(f"{fname[:34]:34} pred={str(pv)[:28]!r:30} truth={tv[:24]!r} [{conf}]")

    print("=" * 78)
    print(f"SCORE vs {os.path.basename(truth_path)}  ({len(truth)} labeled, "
          f"{len(missing)} not found on disk)\n")
    for field in ("company", "designation", "experience"):
        s = stats[field]
        tn, pn, c = s["truth_n"], s["pred_n"], s["correct"]
        rec = c / tn * 100 if tn else 0
        prec = c / pn * 100 if pn else 0
        print(f"{field.upper()}  (labeled={tn})")
        print(f"   recall    {c}/{tn}  {rec:3.0f}%   (correct / all labeled)")
        print(f"   precision {c}/{pn}  {prec:3.0f}%   (correct / extractor produced a value)")
        for conf in ("high", "medium", "none"):
            if conf in s["conf"]:
                ok, tot = s["conf"][conf]
                print(f"      conf={conf:<6} {ok}/{tot}  {ok/tot*100:3.0f}% correct")
        print()
    for field in ("company", "designation", "experience"):
        if mism[field]:
            print(f"--- {field} mismatches (extractor produced a WRONG value) ---")
            for m in mism[field][:20]:
                print("  " + m)
            print()


# --------------------------------------------------------------------------- #
def find_cvs(root):
    out = []
    for dp, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith((".pdf", ".docx")):
                out.append(os.path.join(dp, f))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--engine", default="pdfminer", choices=["pdfminer", "fitz"])
    ap.add_argument("--limit", type=int, default=40, help="max CVs to process")
    ap.add_argument("--show", type=int, default=20, help="how many to print in detail")
    ap.add_argument("--csv", help="write a labeling sheet (one openable row per CV "
                                  "with blank *_TRUE columns to fill in)")
    ap.add_argument("--truth", help="score extraction vs a hand-labeled truth CSV "
                                    "(company_TRUE/designation_TRUE/experience_TRUE)")
    args = ap.parse_args()

    if args.truth:
        run_score(args.truth, args.dir, args.engine)
        return

    print(f"skills gazetteer: {len(SKILLS)}   titles gazetteer: {len(TITLES)}")
    cvs = find_cvs(args.dir)[: args.limit]
    print(f"processing {len(cvs)} CV(s) with engine={args.engine}\n")

    rows = []
    cov = {"skills": 0, "designation": 0, "experience": 0, "company": 0}
    n = 0
    for i, path in enumerate(cvs):
        text = extract_text(path, args.engine)
        if not text or len(text) < 50:
            continue
        n += 1
        r = parse_fields(text, os.path.basename(path))
        if r["skills"]:
            cov["skills"] += 1
        if r["designation"]:
            cov["designation"] += 1
        if r["experience"] is not None:
            cov["experience"] += 1
        if r["company"]:
            cov["company"] += 1
        if args.csv:
            rows.append({
                "file": os.path.basename(path),
                "path": os.path.abspath(path),
                "company": r["company"] or "",
                "company_conf": r["company_conf"] or "",
                "company_TRUE": "",
                "designation": r["designation"] or "",
                "designation_conf": r["designation_conf"] or "",
                "designation_TRUE": "",
                "experience": r["experience"] if r["experience"] is not None else "",
                "experience_conf": r["experience_conf"] or "",
                "experience_TRUE": "",
                "skills_n": len(r["skills"]),
                "skills_sample": ", ".join(r["skills"][:10]),
                "sections": ", ".join(r["sections"]),
            })
        if i < args.show:
            print("=" * 78)
            print(os.path.basename(path)[:76])
            print(f"  sections   : {r['sections']}")
            print(f"  designation: {r['designation']}  [{r['designation_conf']}]")
            print(f"  company    : {r['company']}  [{r['company_conf']}]")
            print(f"  experience : {r['experience']}  [{r['experience_conf']}]")
            print(f"  skills[{len(r['skills'])}] : {', '.join(r['skills'][:12])}")

    print("\n" + "=" * 78)
    print(f"COVERAGE over {n} CV(s) (field was found / non-empty):")
    for k, v in cov.items():
        pct = (v / n * 100) if n else 0
        print(f"  {k:<12} {v:>3}/{n}  {pct:>3.0f}%")
    print("=" * 78)
    print("NOTE: coverage != accuracy. No labels exist for these fields; eyeball above.")

    if args.csv and rows:
        cols = ["file", "path", "company", "company_conf", "company_TRUE",
                "designation", "designation_conf", "designation_TRUE",
                "experience", "experience_conf", "experience_TRUE",
                "skills_n", "skills_sample", "sections"]
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote labeling sheet -> {os.path.abspath(args.csv)}  ({len(rows)} rows)")
        print("Fill the *_TRUE columns by opening each CV via its 'path'; "
              "blank TRUE = field genuinely absent.")


if __name__ == "__main__":
    main()
