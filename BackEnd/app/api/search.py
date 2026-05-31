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

@router.get("/search-cvs")
def search_cvs(
    query: str = Query(..., description="Conversational query or keyword boolean string"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    batch_min: Optional[int] = Query(None, description="Minimum graduation batch year (1950-2030)"),
    batch_max: Optional[int] = Query(None, description="Maximum graduation batch year (1950-2030)"),
    last_education: Optional[str] = Query(None, description="Last education filter (case-insensitive substring match)"),
    upload_range: Optional[str] = Query(None, description="Upload date range: 1m, 3m, 6m, 1y, 2y, 2y+"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Run the query through our semantic translator first
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
    
    required_tags = []
    if tags and tags.strip():
        required_tags = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]

    now = datetime.utcnow()
    upload_threshold = None
    upload_comparison = None
    
    if upload_range and upload_range.strip():
        if upload_range == "1m":
            upload_threshold = now - timedelta(days=30)
            upload_comparison = "after"
        elif upload_range == "3m":
            upload_threshold = now - timedelta(days=90)
            upload_comparison = "after"
        elif upload_range == "6m":
            upload_threshold = now - timedelta(days=180)
            upload_comparison = "after"
        elif upload_range == "1y":
            upload_threshold = now - timedelta(days=365)
            upload_comparison = "after"
        elif upload_range == "2y":
            upload_threshold = now - timedelta(days=730)
            upload_comparison = "after"
        elif upload_range == "2y+":
            upload_threshold = now - timedelta(days=730)
            upload_comparison = "before"

    results = []
    total_cvs = 0
    filtered_cvs = 0

    filter_stats = {
        "total_cvs": 0,
        "completed_processing": 0,
        "passed_tag_filter": 0,
        "passed_batch_filter": 0,
        "passed_education_filter": 0,
        "passed_upload_filter": 0,
        "passed_keyword_filter": 0,
        "final_results": 0
    }

    for cv in db.cvs.find():
        filter_stats["total_cvs"] += 1
        
        if cv.get("processing_status") != "completed":
            continue
        filter_stats["completed_processing"] += 1
        
        raw_text = cv.get("raw_text") or ""
        cv_tags = [t.lower() for t in cv.get("tags", [])]
        cv_skills = [s.lower() for s in cv.get("skills", [])]
        
        if required_tags:
            if not all(tag in cv_tags for tag in required_tags):
                continue
        filter_stats["passed_tag_filter"] += 1

        batch = cv.get("graduation_batch")
        try:
            batch = int(batch) if batch else None
        except (TypeError, ValueError):
            batch = None

        if batch is not None and (batch < 1950 or batch > 2030):
            batch = None

        if batch_min is not None and (batch is None or batch < batch_min):
            continue
        if batch_max is not None and (batch is None or batch > batch_max):
            continue
        filter_stats["passed_batch_filter"] += 1

        # Education filter - fallback to semantic keywords if no explicit parameter passed
        if last_education and last_education.strip():
            le = (cv.get("last_education") or "").lower()
            if last_education.lower() not in le:
                continue
        elif is_conversational and semantic_edu_kws:
            le = (cv.get("last_education") or "").lower()
            if not any(edu in le for edu in semantic_edu_kws):
                continue
        filter_stats["passed_education_filter"] += 1

        # Semantic Sourcing Filters
        # Experience constraints
        cv_exp = cv.get("total_experience_years")
        try:
            cv_exp = int(cv_exp) if cv_exp is not None else 0
        except (TypeError, ValueError):
            cv_exp = 0

        if is_conversational and semantic_exp_min is not None:
            if cv_exp < semantic_exp_min:
                continue

        # Technical skills constraints
        if is_conversational and semantic_skills:
            if not any(skill in cv_skills or skill in raw_text.lower() for skill in semantic_skills):
                continue

        upload_time = cv.get("upload_time")
        if isinstance(upload_time, str):
            try:
                upload_time = datetime.fromisoformat(upload_time.replace('Z', '+00:00'))
            except ValueError:
                upload_time = None

        if upload_range and upload_range.strip() and upload_threshold:
            if upload_comparison == "after":
                if not upload_time or upload_time < upload_threshold:
                    continue
            elif upload_comparison == "before":
                if upload_time and upload_time > upload_threshold:
                    continue
        filter_stats["passed_upload_filter"] += 1

        if search_in_text(raw_text, keywords, mode):
            filter_stats["passed_keyword_filter"] += 1
            
            score = compute_match_score(
                cv_text=raw_text,
                query=query,
                skills=cv.get("skills", []),
                position=cv.get("current_position"),
                company=cv.get("current_company"),
                name=cv.get("name"),
                email=cv.get("email")
            )
            
            result = {
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
            }
            results.append(result)
            filter_stats["final_results"] += 1

    results.sort(key=lambda x: x["match_score"], reverse=True)

    return JSONResponse(content=jsonable_encoder({
        "results": results,
        "search_info": {
            "query": query,
            "keywords": keywords,
            "mode": mode,
            "is_conversational": is_conversational,
            "semantic_extracted": {
                "skills": semantic_skills,
                "experience_min": semantic_exp_min,
                "education_keywords": semantic_edu_kws
            } if is_conversational else None,
            "filters_applied": {
                "tags": tags if tags and tags.strip() else None,
                "batch_min": batch_min,
                "batch_max": batch_max,
                "last_education": last_education if last_education and last_education.strip() else None,
                "upload_range": upload_range if upload_range and upload_range.strip() else None
            },
            "active_filters": {
                "tags_active": bool(required_tags),
                "batch_min_active": batch_min is not None,
                "batch_max_active": batch_max is not None,
                "education_active": bool(last_education and last_education.strip()),
                "upload_range_active": bool(upload_range and upload_range.strip() and upload_threshold)
            }
        },
        "filter_stats": filter_stats
    }))


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