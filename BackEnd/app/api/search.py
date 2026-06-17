from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Optional
from datetime import datetime, timedelta
import re

from app.db.mongodb import db
from app.utils.auth import decode_token
from app.utils.scorer import compute_match_score
from app.utils.query_translator import translate_conversational_query

router = APIRouter()
security = HTTPBearer()

def parse_boolean_query(query: str):
    """Parse boolean query and return keywords and mode"""
    # Handle quoted phrases
    quoted_phrases = re.findall(r'"([^"]*)"', query)
    
    # Remove quoted phrases from query temporarily
    temp_query = query
    for phrase in quoted_phrases:
        temp_query = temp_query.replace(f'"{phrase}"', '')
    
    if ' or ' in temp_query.lower():
        keywords = [kw.strip().lower() for kw in temp_query.split(' or ') if kw.strip()]
        mode = 'OR'
    elif ' and ' in temp_query.lower():
        keywords = [kw.strip().lower() for kw in temp_query.split(' and ') if kw.strip()]
        mode = 'AND'
    else:
        keywords = [kw.strip().lower() for kw in temp_query.split() if kw.strip()]
        mode = 'AND'
    
    # Add quoted phrases back as single keywords
    keywords.extend([phrase.lower() for phrase in quoted_phrases])
    
    return keywords, mode

def search_in_text(text: str, keywords: list, mode: str) -> bool:
    """Search for keywords in text with better matching"""
    if not keywords:
        return False
    
    text_lower = text.lower()
    
    if mode == "AND":
        # All keywords must be present
        for keyword in keywords:
            if keyword and keyword not in text_lower:
                return False
        return True
    else:  # OR mode
        # At least one keyword must be present
        for keyword in keywords:
            if keyword and keyword in text_lower:
                return True
        return False

SEARCH_FETCH_LIMIT = 500  # Max docs fetched from MongoDB before Python scoring

@router.get("/search-cvs")
def search_cvs(
    query: Optional[str] = Query(None, description="Conversational query or keyword boolean string"),
    tags: Optional[str] = Query(None),
    batch_min: Optional[int] = Query(None),
    batch_max: Optional[int] = Query(None),
    last_education: Optional[str] = Query(None),
    upload_range: Optional[str] = Query(None),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    query = (query or "").strip()
    keyword_search = bool(query)

    if keyword_search:
        translation = translate_conversational_query(query)
        is_conversational = translation.get("is_conversational", False)
        if is_conversational:
            keywords = translation.get("keywords", [])
            mode = "OR" if len(keywords) > 1 else "AND"
            semantic_skills = [s.lower() for s in translation.get("skills", [])]
            semantic_exp_min = translation.get("experience_min")
            semantic_edu_kws = [e.lower() for e in translation.get("education_keywords", [])]
        else:
            keywords, mode = parse_boolean_query(query)
            semantic_skills = []
            semantic_exp_min = None
            semantic_edu_kws = []
    else:
        is_conversational = False
        keywords = []
        mode = "AND"
        semantic_skills = []
        semantic_exp_min = None
        semantic_edu_kws = []

    required_tags = [t.strip().lower() for t in tags.split(',') if t.strip()] if tags and tags.strip() else []

    now = datetime.utcnow()
    upload_threshold = None
    upload_comparison = None
    upload_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}
    if upload_range and upload_range.strip():
        if upload_range in upload_days:
            upload_threshold = now - timedelta(days=upload_days[upload_range])
            upload_comparison = "after"
        elif upload_range == "2y+":
            upload_threshold = now - timedelta(days=730)
            upload_comparison = "before"

    # --- Build MongoDB filter (structural filters only) ---
    mongo_filter = {"processing_status": "completed"}

    if required_tags:
        mongo_filter["tags"] = {"$all": required_tags}

    batch_range = {}
    if batch_min is not None:
        batch_range["$gte"] = batch_min
    if batch_max is not None:
        batch_range["$lte"] = batch_max
    if batch_range:
        mongo_filter["graduation_batch"] = batch_range

    if last_education and last_education.strip():
        mongo_filter["last_education"] = {"$regex": last_education.strip(), "$options": "i"}
    elif is_conversational and semantic_edu_kws:
        mongo_filter["last_education"] = {"$regex": "|".join(semantic_edu_kws), "$options": "i"}

    if upload_threshold:
        op = "$gte" if upload_comparison == "after" else "$lte"
        mongo_filter["upload_time"] = {op: upload_threshold}

    if is_conversational and semantic_exp_min is not None:
        mongo_filter["total_experience_years"] = {"$gte": semantic_exp_min}

    if is_conversational and semantic_skills:
        mongo_filter["skills"] = {"$in": semantic_skills}

    # --- Fetch from MongoDB (capped at SEARCH_FETCH_LIMIT) ---
    cursor = db.cvs.find(mongo_filter).limit(SEARCH_FETCH_LIMIT)

    # --- Python: keyword matching + scoring ---
    results = []
    db_count = 0

    for cv in cursor:
        db_count += 1
        raw_text = cv.get("raw_text") or ""

        if keyword_search and not search_in_text(raw_text, keywords, mode):
            continue

        score = compute_match_score(
            cv_text=raw_text,
            query=query,
            skills=cv.get("skills", []),
            position=cv.get("current_position"),
            company=cv.get("current_company"),
            name=cv.get("name"),
            email=cv.get("email")
        ) if keyword_search else 0

        results.append({
            "_id": str(cv["_id"]),
            "user_email": cv.get("user_email"),
            "original_filename": cv.get("original_filename"),
            "stored_filename": cv.get("stored_filename"),
            "match_score": score,
            "upload_time": cv.get("upload_time"),
            "name": cv.get("name"),
            "email": cv.get("email"),
            "phone": cv.get("phone"),
            "skills": cv.get("skills", []),
            "current_position": cv.get("current_position"),
            "current_company": cv.get("current_company"),
            "last_education": cv.get("last_education"),
            "graduation_batch": cv.get("graduation_batch"),
            "tags": cv.get("tags", []),
            "raw_text_preview": raw_text[:200] + "..." if len(raw_text) > 200 else raw_text,
            "processing_status": cv.get("processing_status")
        })

    if keyword_search:
        results.sort(key=lambda x: x["match_score"], reverse=True)
    else:
        results.sort(key=lambda x: x["upload_time"] or "", reverse=True)

    total_matching = len(results)
    skip = (page - 1) * limit
    page_results = results[skip: skip + limit]

    return JSONResponse(content=jsonable_encoder({
        "results": page_results,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_matching": total_matching,
            "total_pages": max(1, -(-total_matching // limit)),
            "has_next": skip + limit < total_matching,
            "has_prev": page > 1,
        },
        "search_info": {
            "query": query,
            "keywords": keywords,
            "mode": mode,
            "is_conversational": is_conversational,
            "db_scanned": db_count,
            "filters_applied": {
                "tags": tags if required_tags else None,
                "batch_min": batch_min,
                "batch_max": batch_max,
                "last_education": last_education if last_education and last_education.strip() else None,
                "upload_range": upload_range if upload_threshold else None,
            },
        },
    }))


@router.get("/tags")
def get_all_tags(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = decode_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    tags = db.cvs.distinct("tags")
    return sorted([t for t in tags if t])


@router.get("/debug-cv/{cv_id}")
def debug_cv(
    cv_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Debug endpoint to check a specific CV's content"""
    token = credentials.credentials
    user_data = decode_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    from bson import ObjectId
    try:
        cv = db.cvs.find_one({"_id": ObjectId(cv_id)})
        if not cv:
            raise HTTPException(status_code=404, detail="CV not found")
        
        return JSONResponse(content=jsonable_encoder({
            "cv_id": cv_id,
            "processing_status": cv.get("processing_status"),
            "raw_text": cv.get("raw_text"),
            "name": cv.get("name"),
            "email": cv.get("email"),
            "tags": cv.get("tags", []),
            "skills": cv.get("skills", []),
            "graduation_batch": cv.get("graduation_batch"),
            "last_education": cv.get("last_education"),
            "upload_time": cv.get("upload_time"),
            "user_email": cv.get("user_email")
        }))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CV ID: {str(e)}")