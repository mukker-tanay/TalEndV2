import re
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

stop_words = set(stopwords.words('english'))

def clean_and_tokenize(text: str):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = word_tokenize(text)
    return [t for t in tokens if t not in stop_words and len(t) > 1]

def compute_match_score(cv_text: str, query: str, skills=None, position=None, company=None, name=None, email=None) -> float:
    score = 0.0
    query_tokens = set(clean_and_tokenize(query))
    cv_tokens = set(clean_and_tokenize(cv_text))

    # 1. Text match (Jaccard-based)
    if query_tokens and cv_tokens:
        intersection = len(query_tokens & cv_tokens)
        jaccard_score = (intersection / len(query_tokens)) * 5  # Scale to 5
        score += jaccard_score

    # 2. Skill match
    if skills:
        skill_text = ' '.join(skills)
        skill_tokens = set(clean_and_tokenize(skill_text))
        match_count = len(query_tokens & skill_tokens)
        score += min(2.0, match_count * 0.5)  # 0.5 per skill match

    # 3. Position/Company
    if position:
        position_tokens = set(clean_and_tokenize(position))
        score += min(1.0, len(query_tokens & position_tokens) * 0.5)

    if company:
        company_tokens = set(clean_and_tokenize(company))
        score += min(1.0, len(query_tokens & company_tokens) * 0.5)

    # 4. Bonus: name/email (rare)
    bonus_fields = f"{name or ''} {email or ''}"
    bonus_tokens = set(clean_and_tokenize(bonus_fields))
    if query_tokens & bonus_tokens:
        score += 1.0

    return round(min(score, 10.0), 2)
