import os
import json
import re
import requests
import sentry_sdk
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def extract_fields_with_gemini(cv_text: str) -> dict:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
    }

    prompt = f"""
You are a CV parser. Given the following resume text, extract only the following fields:
- Full Name
- Current Company
- Current Designation
- Last Education Degree and Institute (most recent degree including college/university name)
- Graduation Year or Batch for the last degree (if mentioned)
- Total Experience (in years)
- Skills (as a list of strings)

Return only a valid JSON in this format (keys must match exactly), without any markdown or code block formatting:
{{
    "name": "Full Name",
    "current_company": "Company Name",
    "current_designation": "Designation Title",
    "last_education": "Last Education Degree and Institute",
    "batch": "Graduation Year or Batch",
    "Total_Experience": "Total Experience (in years)",
    "skills": ["Skill1", "Skill2", "Skill3", ...]
}}

Resume text:
\"\"\"{cv_text}\"\"\"
"""

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    try:
        response = requests.post(
            f"{endpoint}?key={GEMINI_API_KEY}",
            headers=headers,
            data=json.dumps(payload)
        )

        result = response.json()
        print("GEMINI RAW RESPONSE:", json.dumps(result, indent=2))

        candidates = result.get("candidates")
        if not candidates or "content" not in candidates[0]:
            raise ValueError("Missing 'candidates' or 'content' in response.")

        content = candidates[0]["content"]
        parts = content.get("parts", [])
        if not parts or "text" not in parts[0]:
            raise ValueError("Missing 'parts' or 'text' in content.")

        raw_text = parts[0]["text"].strip()

        match = re.match(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
        if match:
            raw_text = match.group(1).strip()

        parsed_json = json.loads(raw_text)
        return parsed_json

    except Exception as e:
        print("Gemini parsing failed:", e)
        sentry_sdk.capture_message(
            f"Gemini full CV parse failed: {e}",
            level="error"
        )
        return {
            "name": None,
            "current_company": None,
            "current_designation": None,
            "last_education": None,
            "batch": None,
            "Total_Experience": None,
            "skills": []
        }


def extract_name_with_gemini(cv_text: str) -> str | None:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    prompt = f"""Look at the beginning of this resume and find the candidate's full name.
Return only the full name as a plain string. No explanation, no JSON, just the name.
If you truly cannot find a name, return null.

Resume text:
\"\"\"{cv_text[:600]}\"\"\"
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(
            f"{endpoint}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        result = response.json()
        candidates = result.get("candidates")
        if not candidates or "content" not in candidates[0]:
            return None
        text = candidates[0]["content"]["parts"][0]["text"].strip()
        if text.lower() in ("null", "none", ""):
            return None
        return text
    except Exception as e:
        print("Gemini name extraction failed:", e)
        sentry_sdk.capture_message(
            f"Gemini focused name extraction failed: {e}",
            level="error"
        )
        return None
