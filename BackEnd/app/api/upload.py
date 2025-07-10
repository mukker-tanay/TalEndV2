from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from uuid import uuid4
import zipfile
from tempfile import TemporaryDirectory
import os
from datetime import datetime
from bson import ObjectId
from typing import Optional
import json

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

UPLOAD_DIR = "uploaded_cvs"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-cv")
async def upload_cv(
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
        # Save temporarily for parsing
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract name/email/phone for duplicate check
        text = extract_text_from_pdf(temp_path) if ext.lower() == ".pdf" else extract_text_from_docx(temp_path)
        parsed_data = parse_cv_enhanced(text)

        name = parsed_data.get("name", "").strip().lower()
        email = parsed_data.get("email", "").strip().lower()
        phone = parsed_data.get("phone", "").strip()

        if not email and not phone:
            raise HTTPException(status_code=400, detail="Email or phone number is required in CV for deduplication.")

        # Check for duplicate
        existing_cv = db.cvs.find_one({
            "user_email": user_email,
            "$or": [
                {"email": email},
                {"phone": phone}
            ]
        })

        # Remove old entry if found
        if existing_cv:
            old_file = existing_cv.get("stored_filename")
            if old_file:
                old_path = os.path.join(UPLOAD_DIR, old_file)
                if os.path.exists(old_path):
                    os.remove(old_path)
            db.cvs.delete_one({"_id": existing_cv["_id"]})

        # Final filename after resolving conflicts
        final_filename = original_name
        final_path = os.path.join(UPLOAD_DIR, final_filename)
        counter = 1
        while os.path.exists(final_path):
            name_part, ext = os.path.splitext(original_name)
            final_filename = f"{name_part}_{counter}{ext}"
            final_path = os.path.join(UPLOAD_DIR, final_filename)
            counter += 1

        # Rename temp file to final filename
        os.rename(temp_path, final_path)

        tags_list = []
        if tags:
            try:
                tags_list = json.loads(tags)
                if not isinstance(tags_list, list):
                    tags_list = []
            except Exception:
                tags_list = []

        # Insert new entry
        db_entry = {
            "user_email": user_email,
            "original_filename": original_name,
            "stored_filename": final_filename,
            "file_size": file.size,
            "file_type": final_filename.split(".")[-1].lower(),
            "upload_time": datetime.utcnow(),
            "processing_status": "uploaded",
            "tags": tags_list,
            "name": name,
            "email": email,
            "phone": phone
        }
        result = db.cvs.insert_one(db_entry)
        cv_id = str(result.inserted_id)

        # Start background parse
        parse_cv_task.delay(str(cv_id), final_path, original_name)

        return {
            "message": "CV uploaded successfully (duplicate replaced if found).",
            "cv_id": cv_id,
            "status": "uploaded"
        }

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
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
            "tags": cv.get("tags", [])
        })

    return result


@router.get("/cv/download/{filename}")
def download_cv(filename: str):
    path = os.path.join(UPLOAD_DIR, filename)
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
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path, media_type="application/pdf")

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

@router.post("/upload-zip")
async def upload_zip(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed.")

    temp_dir = TemporaryDirectory()
    try:
        zip_path = os.path.join(temp_dir.name, file.filename)
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir.name)

        uploaded_cvs = []
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
                        "tags": []
                    }
                    result = db.cvs.insert_one(db_entry)
                    cv_id = str(result.inserted_id)

                    parse_cv_task.delay(cv_id, dst_path, orig_name)
                    uploaded_cvs.append({
                        "cv_id": cv_id,
                        "original_filename": orig_name,
                        "status": "uploaded"
                    })

        if not uploaded_cvs:
            raise HTTPException(status_code=400, detail="No valid CV files found in ZIP.")

        return {
            "message": f"{len(uploaded_cvs)} CVs uploaded from ZIP.",
            "uploaded": uploaded_cvs
        }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling ZIP: {str(e)}")
    finally:
        temp_dir.cleanup()