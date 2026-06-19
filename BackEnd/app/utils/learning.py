import datetime
import re
from app.db.mongodb import db

# Collection names
KNOWN_COMPANIES_COLL = "known_companies"
CUSTOM_TITLES_COLL = "custom_job_titles"
NAME_MAPPINGS_COLL = "name_mappings"

def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower()).strip()

def learn_company(corrected: str):
    """Register a user-verified company name in the database."""
    if not corrected:
        return
    norm = normalize_text(corrected)
    if not norm or len(norm) < 3:
        return
    
    # Check if already exists
    exists = db[KNOWN_COMPANIES_COLL].find_one({"normalized": norm})
    if not exists:
        db[KNOWN_COMPANIES_COLL].insert_one({
            "company_name": corrected.strip(),
            "normalized": norm,
            "added_at": datetime.datetime.utcnow()
        })

def learn_designation(corrected: str):
    """Register a user-verified job title in the database."""
    if not corrected:
        return
    norm = normalize_text(corrected)
    if not norm or len(norm) < 3:
        return
        
    exists = db[CUSTOM_TITLES_COLL].find_one({"normalized": norm})
    if not exists:
        db[CUSTOM_TITLES_COLL].insert_one({
            "title": corrected.strip(),
            "normalized": norm,
            "added_at": datetime.datetime.utcnow()
        })

def _get_filename_key(filename: str) -> str:
    """Derive a normalized key from filename tokens for mapping."""
    if not filename:
        return ""
    from app.utils.name_resolver import _fname_name_tokens
    toks = _fname_name_tokens(filename)
    if not toks:
        return ""
    return "_".join(sorted(t.lower() for t in toks))

def learn_name_mapping(filename: str, email: str, corrected: str):
    """Map filename tokens or email local parts to a verified candidate name."""
    if not corrected:
        return
        
    norm_name = corrected.strip()
    
    # 1. Map by filename key
    fn_key = _get_filename_key(filename)
    if fn_key:
        db[NAME_MAPPINGS_COLL].update_one(
            {"mapping_key": fn_key, "type": "filename"},
            {
                "$set": {
                    "name": norm_name,
                    "updated_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )
        
    # 2. Map by email local part
    if email and "@" in email:
        local_part = email.split("@")[0].lower()
        if len(local_part) > 2:
            db[NAME_MAPPINGS_COLL].update_one(
                {"mapping_key": local_part, "type": "email"},
                {
                    "$set": {
                        "name": norm_name,
                        "updated_at": datetime.datetime.utcnow()
                    }
                },
                upsert=True
            )

def get_known_companies() -> list[str]:
    """Retrieve all verified company names."""
    try:
        docs = db[KNOWN_COMPANIES_COLL].find()
        return [doc["company_name"] for doc in docs if "company_name" in doc]
    except Exception:
        return []

def get_custom_titles() -> set[str]:
    """Retrieve all verified custom job titles as a set."""
    try:
        docs = db[CUSTOM_TITLES_COLL].find()
        return {doc["normalized"] for doc in docs if "normalized" in doc}
    except Exception:
        return set()

def get_name_mapping(filename: str, email: str) -> str:
    """Lookup if this filename or email has a verified name mapping."""
    # Try filename first
    fn_key = _get_filename_key(filename)
    if fn_key:
        match = db[NAME_MAPPINGS_COLL].find_one({"mapping_key": fn_key, "type": "filename"})
        if match:
            return match["name"]
            
    # Try email next
    if email and "@" in email:
        local_part = email.split("@")[0].lower()
        match = db[NAME_MAPPINGS_COLL].find_one({"mapping_key": local_part, "type": "email"})
        if match:
            return match["name"]
            
    return None
