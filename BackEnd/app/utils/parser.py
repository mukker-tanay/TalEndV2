import docx
import re
import spacy
from typing import List, Dict, Optional
import json
import os
import pandas as pd
import fitz  # pymupdf
from app.utils.gemini_parser import extract_fields_with_gemini

nlp = spacy.load("en_core_web_sm")

# Load external datasets
NAMES_DF = pd.read_csv('C:/Users/tanay/Desktop/Data/College/Summer25/TalEnd/BackEnd/paired_full_names.csv', nrows=50000)
FIRST_NAMES_SET = set(NAMES_DF['First Name'].dropna().str.lower())
LAST_NAMES_SET = set(NAMES_DF['Last Name'].dropna().str.lower())

with open('C:/Users/tanay/Desktop/Data/College/Summer25/TalEnd/BackEnd/LINKEDIN_SKILLS_ORIGINAL.txt', encoding='utf-8') as f:
    SKILLS_SET = set(line.strip().lower() for line in f if line.strip())

COLLEGE_DF = pd.read_csv('C:/Users/tanay/Desktop/Data/College/Summer25/TalEnd/BackEnd/world-universities.csv', header=None, names=['country', 'college', 'url'])
COLLEGE_SET = set(COLLEGE_DF['college'].dropna().str.lower())

FORBIDDEN_NAMES = {"chatgpt", "resume", "cv", "profile", "curriculum vitae", "summary", "objective"}


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text("text") or ""
    doc.close()
    return text.strip()


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


def parse_cv_enhanced(text: str, file_name: Optional[str] = None) -> dict:
    doc = nlp(text)
    emails = extract_emails(text)
    phones = extract_phone_numbers(text)
    regex_skills = extract_skills(text)
    education_entries = extract_education(text)

    gemini_data = extract_fields_with_gemini(text)

    parsed_data = {
        "name": gemini_data.get("name"),
        "email": emails[0] if emails else None,
        "emails": emails,
        "phone": phones[0] if phones else None,
        "phone_numbers": phones,
        "skills": gemini_data.get("skills", []) or regex_skills,
        "total_experience_years": gemini_data.get("Total Experience"),
        "current_company": gemini_data.get("current_company"),
        "current_position": gemini_data.get("current_designation"),
        "education": education_entries,
        "last_education": gemini_data.get("last_education"),
        "graduation_batch": gemini_data.get("batch"),
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
