import docx
import re
import sentry_sdk
from typing import List, Dict, Optional
import os
import pandas as pd
import fitz  # pymupdf (font signal + PDF fallback)
from app.utils.gemini_parser import extract_fields_with_gemini
from app.utils.name_resolver import resolve_name
from app.utils.section_parser import resolve_fields

# Base directory (this file is in app/utils/, so go 2 levels up to BackEnd/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

skills_path = os.path.join(BASE_DIR, "../../LINKEDIN_SKILLS_ORIGINAL.txt")
colleges_path = os.path.join(BASE_DIR, "../../world-universities.csv")

with open(skills_path, encoding='utf-8') as f:
    SKILLS_SET = set(line.strip().lower() for line in f if line.strip())

COLLEGE_DF = pd.read_csv(colleges_path, header=None, names=['country', 'college', 'url'])
COLLEGE_SET = set(COLLEGE_DF['college'].dropna().str.lower())

FORBIDDEN_NAMES = {"chatgpt", "resume", "cv", "profile", "curriculum vitae", "summary", "objective"}


def _extract_text_fitz(file_path: str) -> str:
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text("text") or ""
    doc.close()
    return text.strip()


def extract_text_from_pdf(file_path: str) -> str:
    """Extract PDF text, preferring pdfminer.six for reading order.

    pdfminer preserves reading order (the candidate name lands in the first
    lines), which lifts local name accuracy substantially over PyMuPDF's
    geometric block order. fitz is the fast fallback if pdfminer fails/empties.
    """
    try:
        from pdfminer.high_level import extract_text as _pm_extract
        text = (_pm_extract(file_path) or "").strip()
        if text:
            return text
    except Exception:
        pass
    return _extract_text_fitz(file_path)


def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs]).strip()


def extract_emails(text: str) -> List[str]:
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return list(set(re.findall(pattern, text)))


def extract_phone_numbers(text: str) -> List[str]:
    patterns = [
        r'\+91[-\s]?\d{5}\s?\d{5}',
        r'\b91[-\s]?\d{10}\b',
        r'\b[789]\d{9}\b',
        r'\b0\d{2,4}[-\s]?\d{6,8}\b',
        r'\(\d{2,4}\)\s*\d{6,8}',
        r'\+\d{1,4}[-\s]?\d{8,12}',
    ]
    phones = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        phones.extend(matches)
    cleaned = []
    for phone in phones:
        digits = re.sub(r'[^\d]', '', phone)
        if 10 <= len(digits) <= 15:
            cleaned.append(phone.strip())
    return list(set(cleaned))


def extract_skills(text: str) -> List[str]:
    found = set()
    text_lower = text.lower()
    for skill in SKILLS_SET:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            found.add(skill)
    return list(found)


def extract_education(text: str) -> List[Dict[str, str]]:
    education_entries = []
    lines = text.split('\n')
    for line in lines:
        for college in COLLEGE_SET:
            if college in line.lower():
                education_entries.append({'institution': college.title(), 'raw': line.strip()})
    return education_entries


def parse_cv_enhanced(text: str, file_name: Optional[str] = None,
                      file_path: Optional[str] = None) -> dict:
    emails = extract_emails(text)
    phones = extract_phone_numbers(text)
    regex_skills = extract_skills(text)
    education_entries = extract_education(text)

    # Local-first resolution. Name uses the cascade in name_resolver; the rich
    # fields use the section-based extractor in section_parser. Each field carries
    # a confidence; we call Gemini ONCE only if any gated field is not "high"
    # (name low/empty, or company/designation/experience below "high"). When Gemini
    # runs it returns every field, so we fill the gated ones from it (per-field
    # gate). On 126 labeled CVs the local "high" tier is 87-90% precise per field.
    name_info = resolve_name(text, file_name or "", file_path)
    name = name_info["name"]
    name_confidence = name_info["confidence"]
    name_source = name_info["source"]

    field_info = resolve_fields(text, file_name or "")

    need_gemini = (
        name_confidence == "low" or not name
        or field_info["company_confidence"] != "high"
        or field_info["designation_confidence"] != "high"
        or field_info["experience_confidence"] != "high"
    )
    gemini_data = extract_fields_with_gemini(text) if need_gemini else {}

    if not name:
        g_name = gemini_data.get("name")
        if g_name:
            name = g_name
            name_source = "gemini"
        name_confidence = "low"

    # Per-field gate: keep a local "high"; otherwise prefer Gemini, falling back to
    # the local (medium) guess when Gemini didn't return one.
    def _pick(local, local_conf, gem):
        if local_conf == "high":
            return local, "high", "local"
        if gem:
            return gem, "gemini", "gemini"
        if local:
            return local, local_conf or "low", "local"
        return None, None, None

    company, company_conf, company_src = _pick(
        field_info["company"], field_info["company_confidence"],
        gemini_data.get("current_company"))
    position, position_conf, position_src = _pick(
        field_info["designation"], field_info["designation_confidence"],
        gemini_data.get("current_designation"))
    experience, experience_conf, experience_src = _pick(
        field_info["experience"], field_info["experience_confidence"],
        gemini_data.get("Total_Experience"))

    if not name:
        with sentry_sdk.push_scope() as scope:
            scope.set_extra("text_preview", text[:300])
            scope.set_extra("file_name", file_name)
            scope.set_extra("name_confidence", name_confidence)
            sentry_sdk.capture_message(
                "CV name extraction returned empty (local + Gemini)",
                level="warning"
            )

    parsed_data = {
        "name": name,
        "name_confidence": name_confidence,
        "name_source": name_source,
        "email": emails[0] if emails else None,
        "emails": emails,
        "phone": phones[0] if phones else None,
        "phone_numbers": phones,
        "skills": gemini_data.get("skills", []) or regex_skills,
        "total_experience_years": experience,
        "experience_confidence": experience_conf,
        "experience_source": experience_src,
        "current_company": company,
        "company_confidence": company_conf,
        "company_source": company_src,
        "current_position": position,
        "position_confidence": position_conf,
        "position_source": position_src,
        "education": education_entries,
        "last_education": gemini_data.get("last_education"),
        "graduation_batch": gemini_data.get("batch"),
        "sections": field_info["sections"],
        "raw_text": text
    }
    return parsed_data


def test_cv_parser(text: str):
    print("Testing Gemini-enhanced CV Parser\n" + "=" * 50)
    data = parse_cv_enhanced(text)
    print(f"Name: {data['name']}")
    print(f"Email: {data['email']}")
    print(f"Phone: {data['phone']}")
    print(f"Current Company: {data['current_company']}")
    print(f"Current Position: {data['current_position']}")
    print(f"Total Experience: {data['total_experience_years']} years")
    print(f"Last Education: {data['last_education']} ({data['graduation_batch']})")
    print("\nSkills:")
    for skill in data['skills']:
        print(f" - {skill}")
    print(f"\nEducation entries: {len(data['education'])}")
    for edu in data['education']:
        print(f" - {edu}")
