import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def translate_conversational_query(query_text: str) -> dict:
    if not query_text or len(query_text.strip()) < 5:
        return {
            "is_conversational": False,
            "keywords": [],
            "skills": [],
            "experience_min": None,
            "education_keywords": []
        }

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
    }

    prompt = f"""
You are a technical search translator for a recruitment database. Given the following conversational search query from a recruiter, extract the search filters and criteria.

Identify:
1. is_conversational: A boolean representing whether the query is a conversational plain English request (e.g., "React developers with 3 years of experience", "FastAPI coder in Bangalore") rather than a simple keyword string (e.g., "React", "Python").
2. keywords: List of keywords for text matching (e.g., ["react", "python"]).
3. skills: List of specific technical skills mentioned (e.g., ["react", "redux"]).
4. experience_min: The minimum years of experience required as an integer (e.g., 3). If not mentioned, return null.
5. education_keywords: List of degrees or educational institutes mentioned (e.g., ["b.tech", "mba", "iit"]).

Return only a valid JSON in this format (keys must match exactly), without any markdown or code block formatting:
{{
    "is_conversational": true,
    "keywords": ["keyword1", "keyword2"],
    "skills": ["skill1", "skill2"],
    "experience_min": 3,
    "education_keywords": ["edu1", "edu2"]
}}

Recruiter query:
\"\"\"{query_text}\"\"\"
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
            data=json.dumps(payload),
            timeout=10
        )

        result = response.json()
        candidates = result.get("candidates")
        if not candidates or "content" not in candidates[0]:
            raise ValueError("Missing candidates or content in response")

        content = candidates[0]["content"]
        parts = content.get("parts", [])
        if not parts or "text" not in parts[0]:
            raise ValueError("Missing parts or text in content")

        raw_text = parts[0]["text"].strip()

        match = re.match(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
        if match:
            raw_text = match.group(1).strip()

        parsed_json = json.loads(raw_text)
        return parsed_json

    except Exception as e:
        print("Gemini query translation failed:", e)
        return {
            "is_conversational": False,
            "keywords": [],
            "skills": [],
            "experience_min": None,
            "education_keywords": []
        }
