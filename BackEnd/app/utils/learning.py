import datetime
import re
import threading
import time
from app.db.mongodb import db

# Collection names
KNOWN_COMPANIES_COLL = "known_companies"
CUSTOM_TITLES_COLL = "custom_job_titles"
NAME_MAPPINGS_COLL = "name_mappings"

# ---------------------------------------------------------------------------
# In-memory TTL cache for the learned lookups.
# These are read on every CV parse (get_custom_titles runs ~15-20x per CV inside
# the title-matching loop), but they change only when a recruiter verifies a
# field. Caching turns ~20 Mongo reads/CV into ~0, which matters on the small
# VPS. Writes (learn_*) invalidate the relevant key so corrections take effect
# on the very next parse — no stale window.
# ---------------------------------------------------------------------------
_CACHE_TTL = 300  # seconds
_cache = {}       # key -> (expires_at, value)
_cache_lock = threading.Lock()


def _cached(key, loader):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now < hit[0]:
            return hit[1]
    value = loader()  # load outside the lock (Mongo call)
    with _cache_lock:
        _cache[key] = (now + _CACHE_TTL, value)
    return value


def _invalidate(key):
    with _cache_lock:
        _cache.pop(key, None)

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
        _invalidate("known_companies")

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
        _invalidate("custom_titles")

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
        _invalidate("name_mappings")
        
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

def _load_known_companies() -> list[str]:
    try:
        docs = db[KNOWN_COMPANIES_COLL].find()
        return [doc["company_name"] for doc in docs if "company_name" in doc]
    except Exception:
        return []


def get_known_companies() -> list[str]:
    """All verified company names (cached; refreshed on learn_company / TTL)."""
    return _cached("known_companies", _load_known_companies)


def _load_custom_titles() -> set[str]:
    try:
        docs = db[CUSTOM_TITLES_COLL].find()
        return {doc["normalized"] for doc in docs if "normalized" in doc}
    except Exception:
        return set()


def get_custom_titles() -> set[str]:
    """Verified custom job titles (cached; refreshed on learn_designation / TTL)."""
    return _cached("custom_titles", _load_custom_titles)

def _load_name_mappings() -> dict:
    out = {}
    try:
        for d in db[NAME_MAPPINGS_COLL].find():
            key, typ = d.get("mapping_key"), d.get("type")
            if key and typ and d.get("name"):
                out[(typ, key)] = d["name"]
    except Exception:
        pass
    return out


def get_name_mapping(filename: str, email: str) -> str:
    """Lookup if this filename or email has a verified name mapping (cached)."""
    mp = _cached("name_mappings", _load_name_mappings)
    # Try filename first
    fn_key = _get_filename_key(filename)
    if fn_key and ("filename", fn_key) in mp:
        return mp[("filename", fn_key)]

    # Try email next
    if email and "@" in email:
        local_part = email.split("@")[0].lower()
        if ("email", local_part) in mp:
            return mp[("email", local_part)]

    return None
