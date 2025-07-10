import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def extract_fields_with_gemini(cv_text: str) -> dict:
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
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

        # Strip markdown code block if present
        match = re.match(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
        if match:
            raw_text = match.group(1).strip()

        parsed_json = json.loads(raw_text)
        return parsed_json

    except Exception as e:
        print("Gemini parsing failed:", e)
        return {
            "name": None,
            "current_company": None,
            "current_designation": None,
            "last_education": None,
            "batch": None,
            "Total_Experience": None,
            "skills": []
        }
