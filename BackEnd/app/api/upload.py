from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, Request, Body, BackgroundTasks
import threading
import time
import sentry_sdk
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from uuid import uuid4
import zipfile
from tempfile import TemporaryDirectory
import os
import hashlib
import subprocess
from datetime import datetime
from bson import ObjectId
from typing import Optional
from pydantic import BaseModel
import json
from urllib.parse import unquote
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from app.utils.auth import decode_token
from app.utils.parser import (
    extract_text_from_pdf,
    extract_text_from_docx,
    parse_cv_enhanced
)
from app.db.mongodb import db
from app.celery_worker import parse_cv_task

router = APIRouter()
security = HTTPBearer()

UPLOAD_DIR = os.path.realpath("uploaded_cvs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DOCX_CACHE_DIR = os.path.realpath("docx_pdf_cache")
os.makedirs(DOCX_CACHE_DIR, exist_ok=True)


def safe_join(base: str, filename: str) -> str:
    resolved = os.path.realpath(os.path.join(base, filename))
    if not resolved.startswith(base + os.sep) and resolved != base:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return resolved


@router.post("/upload-cv")
@limiter.limit("20/minute")
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    tags: str = Form(None),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename not provided in upload.")

    if file.content_type not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are allowed")

    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size too large. Maximum 10MB allowed")

    original_name = file.filename
    ext = os.path.splitext(original_name)[-1]
    temp_filename = f"temp_{uuid4().hex}{ext}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        text = extract_text_from_pdf(temp_path) if ext.lower() == ".pdf" else extract_text_from_docx(temp_path)
        parsed_data = parse_cv_enhanced(text, file_name=original_name, file_path=temp_path)

        name = (parsed_data.get("name") or "").strip().lower()
        email = (parsed_data.get("email") or "").strip().lower()
        phone = (parsed_data.get("phone") or "").strip()

        if not email and not phone:
            raise HTTPException(status_code=400, detail="Email or phone number is required in CV for deduplication.")

        or_conditions = []
        if email:
            or_conditions.append({"email": email})
        if phone:
            or_conditions.append({"phone": phone})

        existing_cv = db.cvs.find_one({
            "user_email": user_email,
            "$or": or_conditions
        })

        if existing_cv:
            old_file = existing_cv.get("stored_filename")
            if old_file:
                old_path = os.path.join(UPLOAD_DIR, old_file)
                if os.path.exists(old_path):
                    os.remove(old_path)
            db.cvs.delete_one({"_id": existing_cv["_id"]})

        final_filename = original_name
        final_path = os.path.join(UPLOAD_DIR, final_filename)
        counter = 1
        while os.path.exists(final_path):
            name_part, ext = os.path.splitext(original_name)
            final_filename = f"{name_part}_{counter}{ext}"
            final_path = os.path.join(UPLOAD_DIR, final_filename)
            counter += 1

        os.rename(temp_path, final_path)

        tags_list = []
        if tags:
            try:
                tags_list = json.loads(tags)
                if not isinstance(tags_list, list):
                    tags_list = []
            except Exception:
                tags_list = []

        db_entry = {
            "user_email": user_email,
            "original_filename": original_name,
            "stored_filename": final_filename,
            "file_size": file.size,
            "file_type": final_filename.split(".")[-1].lower(),
            "upload_time": datetime.utcnow(),
            "processing_status": "completed",
            "tags": tags_list,
            "raw_text": text,
            "text_length": len(text),
            "name": parsed_data.get("name"),
            "name_confidence": parsed_data.get("name_confidence"),
            "name_source": parsed_data.get("name_source"),
            "email": parsed_data.get("email"),
            "emails": parsed_data.get("emails", []),
            "phone": parsed_data.get("phone"),
            "phone_numbers": parsed_data.get("phone_numbers", []),
            "skills": parsed_data.get("skills", []),
            "current_position": parsed_data.get("current_position"),
            "position_confidence": parsed_data.get("position_confidence"),
            "position_source": parsed_data.get("position_source"),
            "current_company": parsed_data.get("current_company"),
            "company_confidence": parsed_data.get("company_confidence"),
            "company_source": parsed_data.get("company_source"),
            "total_experience_years": parsed_data.get("total_experience_years"),
            "experience_confidence": parsed_data.get("experience_confidence"),
            "experience_source": parsed_data.get("experience_source"),
            "last_education": parsed_data.get("last_education"),
            "graduation_batch": parsed_data.get("graduation_batch"),
            "education": parsed_data.get("education", []),
            "sections": parsed_data.get("sections", {}),
        }
        result = db.cvs.insert_one(db_entry)
        cv_id = str(result.inserted_id)

        try:
            parse_cv_task.delay(str(cv_id), final_path, original_name)
        except Exception:
            pass

        return {
            "message": "CV uploaded and parsed successfully.",
            "cv_id": cv_id,
            "stored_filename": final_filename,
            "status": "completed"
        }

    except HTTPException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("stage", "upload_cv")
            scope.set_extra("original_name", original_name)
            scope.set_user({"email": user_email})
            sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail=f"Error processing CV: {str(e)}")


@router.get("/list-cvs")
def list_user_cvs(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    user_cvs = db.cvs.find({"user_email": user_email})

    result = []
    for cv in user_cvs:
        result.append({
            "id": str(cv["_id"]),
            "filename": cv.get("original_filename"),
            "stored_filename": cv.get("stored_filename"),
            "uploaded_at": cv.get("upload_time").isoformat(),
            "status": cv.get("processing_status", "unknown"),
            "name": cv.get("name"),
            "name_confidence": cv.get("name_confidence"),
            "current_company": cv.get("current_company"),
            "company_confidence": cv.get("company_confidence"),
            "current_position": cv.get("current_position"),
            "position_confidence": cv.get("position_confidence"),
            "total_experience_years": cv.get("total_experience_years"),
            "experience_confidence": cv.get("experience_confidence"),
            "tags": cv.get("tags", [])
        })

    return result


class VerifyCVRequest(BaseModel):
    name: Optional[str] = None
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    total_experience_years: Optional[float] = None


@router.patch("/cv/{cv_id}/verify")
async def verify_cv(
    cv_id: str,
    payload: VerifyCVRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    try:
        cv_data = db.cvs.find_one({
            "_id": ObjectId(cv_id),
            "user_email": user_email
        })
        if not cv_data:
            raise HTTPException(status_code=404, detail="CV not found")

        updates = {}
        from app.utils.learning import learn_company, learn_designation, learn_name_mapping
        
        # 1. Name correction & learning
        if payload.name is not None:
            new_name = payload.name.strip()
            if new_name != cv_data.get("name"):
                updates["name"] = new_name
                updates["name_confidence"] = "high"
                updates["name_source"] = "user"
                learn_name_mapping(
                    cv_data.get("original_filename", ""),
                    cv_data.get("email", ""),
                    new_name
                )
        
        # 2. Company correction & learning
        if payload.current_company is not None:
            new_company = payload.current_company.strip()
            if new_company != cv_data.get("current_company"):
                updates["current_company"] = new_company
                updates["company_confidence"] = "high"
                updates["company_source"] = "user"
                learn_company(new_company)

        # 3. Position/Designation correction & learning
        if payload.current_position is not None:
            new_position = payload.current_position.strip()
            if new_position != cv_data.get("current_position"):
                updates["current_position"] = new_position
                updates["position_confidence"] = "high"
                updates["position_source"] = "user"
                learn_designation(new_position)

        # 4. Experience correction
        if payload.total_experience_years is not None:
            new_exp = payload.total_experience_years
            if new_exp != cv_data.get("total_experience_years"):
                updates["total_experience_years"] = new_exp
                updates["experience_confidence"] = "high"
                updates["experience_source"] = "user"

        if updates:
            db.feedback_logs.insert_one({
                "cv_id": ObjectId(cv_id),
                "user_email": user_email,
                "corrections": updates,
                "timestamp": datetime.utcnow()
            })
            db.cvs.update_one(
                {"_id": ObjectId(cv_id), "user_email": user_email},
                {"$set": updates}
            )

        return {"message": "CV verified and learning registered successfully", "updated": updates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying CV: {str(e)}")


@router.get("/cv/download/{filename}")
def download_cv(filename: str):
    filename = unquote(filename)
    path = safe_join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/octet-stream", filename=filename)


@router.delete("/cv/{cv_id}")
async def delete_cv(
    cv_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    try:
        cv_data = db.cvs.find_one({
            "_id": ObjectId(cv_id),
            "user_email": user_email
        })

        if not cv_data:
            raise HTTPException(status_code=404, detail="CV not found")

        result = db.cvs.delete_one({
            "_id": ObjectId(cv_id),
            "user_email": user_email
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="CV not found")

        if cv_data.get("stored_filename"):
            file_path = os.path.join(UPLOAD_DIR, cv_data["stored_filename"])
            if os.path.exists(file_path):
                os.remove(file_path)

        return {
            "message": "CV deleted successfully",
            "deleted_cv": {
                "cv_id": cv_id,
                "original_filename": cv_data.get("original_filename"),
                "upload_time": cv_data.get("upload_time")
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting CV: {str(e)}")

@router.get("/cv/preview/{filename}")
def preview_cv(filename: str):
    filename = unquote(filename)
    path = safe_join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )

@router.get("/cv/preview-docx/{filename}")
def preview_docx(filename: str):
    filename = unquote(filename)
    docx_path = safe_join(UPLOAD_DIR, filename)
    if not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="File not found")

    with open(docx_path, "rb") as f:
        cache_key = hashlib.md5(f.read()).hexdigest()
    pdf_path = os.path.join(DOCX_CACHE_DIR, f"{cache_key}.pdf")

    if not os.path.exists(pdf_path):
        try:
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", DOCX_CACHE_DIR, docx_path],
                capture_output=True, timeout=60
            )
            base = os.path.splitext(os.path.basename(docx_path))[0]
            lo_output = os.path.join(DOCX_CACHE_DIR, f"{base}.pdf")
            if os.path.exists(lo_output):
                os.rename(lo_output, pdf_path)
            else:
                raise HTTPException(status_code=500, detail="Conversion failed")
        except FileNotFoundError:
            raise HTTPException(status_code=501, detail="LibreOffice not installed on server")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Conversion timed out")

    return FileResponse(pdf_path, media_type="application/pdf", headers={"Content-Disposition": "inline"})

@router.get("/cv-status/{cv_id}")
def cv_status(cv_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")
    cv = db.cvs.find_one({"_id": ObjectId(cv_id), "user_email": user_email})
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")
    return {
        "status": cv.get("processing_status", "unknown"),
        "error": cv.get("error"),
        "cv_id": cv_id
    }

def _parse_and_store_cv(cv_id: str, file_path: str, original_name: str):
    try:
        ext = file_path.split(".")[-1].lower()
        text = extract_text_from_pdf(file_path) if ext == "pdf" else extract_text_from_docx(file_path)
        if not text or len(text.strip()) < 50:
            db.cvs.update_one(
                {"_id": ObjectId(cv_id)},
                {"$set": {"processing_status": "error", "error": "Insufficient text extracted"}}
            )
            return
        parsed_data = parse_cv_enhanced(text, file_name=original_name, file_path=file_path)
        update_fields = {
            "processing_status": "completed",
            "raw_text": text,
            "text_length": len(text),
            "name": parsed_data.get("name"),
            "name_confidence": parsed_data.get("name_confidence"),
            "name_source": parsed_data.get("name_source"),
            "email": parsed_data.get("email"),
            "emails": parsed_data.get("emails", []),
            "phone": parsed_data.get("phone"),
            "phone_numbers": parsed_data.get("phone_numbers", []),
            "skills": parsed_data.get("skills", []),
            "current_position": parsed_data.get("current_position"),
            "position_confidence": parsed_data.get("position_confidence"),
            "position_source": parsed_data.get("position_source"),
            "current_company": parsed_data.get("current_company"),
            "company_confidence": parsed_data.get("company_confidence"),
            "company_source": parsed_data.get("company_source"),
            "total_experience_years": parsed_data.get("total_experience_years"),
            "experience_confidence": parsed_data.get("experience_confidence"),
            "experience_source": parsed_data.get("experience_source"),
            "last_education": parsed_data.get("last_education"),
            "graduation_batch": parsed_data.get("graduation_batch"),
            "education": parsed_data.get("education", []),
            "sections": parsed_data.get("sections", {}),
        }
        db.cvs.update_one({"_id": ObjectId(cv_id)}, {"$set": update_fields})
    except Exception as e:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("stage", "background_parse")
            scope.set_extra("cv_id", cv_id)
            scope.set_extra("original_name", original_name)
            sentry_sdk.capture_exception(e)
        db.cvs.update_one(
            {"_id": ObjectId(cv_id)},
            {"$set": {"processing_status": "error", "error": str(e)}}
        )


def _parse_queue(cv_queue: list, batch_size: int = 5):
    """Process a list of (cv_id, file_path, original_name) tuples, batch_size at a time."""
    for i in range(0, len(cv_queue), batch_size):
        batch = cv_queue[i:i + batch_size]
        threads = [
            threading.Thread(target=_parse_and_store_cv, args=(cv_id, path, name))
            for cv_id, path, name in batch
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if i + batch_size < len(cv_queue):
            time.sleep(15)


@router.post("/upload-zip")
async def upload_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: str = Form(None),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed.")

    tags_list = []
    if tags:
        try:
            tags_list = json.loads(tags)
            if not isinstance(tags_list, list):
                tags_list = []
        except Exception:
            tags_list = []

    temp_dir = TemporaryDirectory()
    try:
        zip_path = os.path.join(temp_dir.name, file.filename)
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir.name)

        uploaded_cvs = []
        cv_queue = []
        for root, _, files in os.walk(temp_dir.name):
            for name in files:
                if name.lower().endswith((".pdf", ".docx")):
                    orig_name = name
                    new_filename = f"{uuid4().hex}_{name}"
                    src_path = os.path.join(root, name)
                    dst_path = os.path.join(UPLOAD_DIR, new_filename)
                    os.rename(src_path, dst_path)

                    db_entry = {
                        "user_email": user_email,
                        "original_filename": orig_name,
                        "stored_filename": new_filename,
                        "file_size": os.path.getsize(dst_path),
                        "file_type": orig_name.split(".")[-1].lower(),
                        "upload_time": datetime.utcnow(),
                        "processing_status": "uploaded",
                        "tags": tags_list
                    }
                    result = db.cvs.insert_one(db_entry)
                    cv_id = str(result.inserted_id)
                    cv_queue.append((cv_id, dst_path, orig_name))
                    uploaded_cvs.append({
                        "cv_id": cv_id,
                        "original_filename": orig_name,
                        "status": "uploaded"
                    })

        if not uploaded_cvs:
            raise HTTPException(status_code=400, detail="No valid CV files found in ZIP.")

        background_tasks.add_task(_parse_queue, cv_queue)

        return {
            "message": f"{len(uploaded_cvs)} CVs uploaded from ZIP.",
            "uploaded": uploaded_cvs
        }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file.")
    except HTTPException:
        raise
    except Exception as e:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("stage", "upload_zip")
            scope.set_extra("zip_filename", file.filename)
            scope.set_user({"email": user_email})
            sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail=f"Error handling ZIP: {str(e)}")
    finally:
        temp_dir.cleanup()


@router.post("/reparse-stuck")
async def reparse_stuck_cvs(
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    stuck = list(db.cvs.find({
        "user_email": user_email,
        "$or": [
            {"processing_status": "uploaded"},
            {"processing_status": "completed", "name": {"$in": [None, ""]}}
        ]
    }))
    cv_queue = []
    for cv in stuck:
        cv_id = str(cv["_id"])
        file_path = os.path.join(UPLOAD_DIR, cv.get("stored_filename", ""))
        if os.path.exists(file_path):
            cv_queue.append((cv_id, file_path, cv.get("original_filename", "")))
    count = len(cv_queue)
    if cv_queue:
        background_tasks.add_task(_parse_queue, cv_queue)
    return {"message": f"Re-parsing {count} stuck CV(s) in background."}


@router.patch("/cv/{cv_id}/tags")
async def update_cv_tags(
    cv_id: str,
    tags: list[str] = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    try:
        result = db.cvs.update_one(
            {"_id": ObjectId(cv_id), "user_email": user_email},
            {"$set": {"tags": tags}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="CV not found")
        return {"message": "Tags updated successfully", "tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating tags: {str(e)}")