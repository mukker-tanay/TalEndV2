import os
from dotenv import load_dotenv
load_dotenv()

from celery import Celery
from app.utils.parser import extract_text_from_pdf, extract_text_from_docx, parse_cv_enhanced
from app.db.mongodb import db
from bson import ObjectId

celery_app = Celery(
    'talend',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def parse_cv_task(cv_id, file_path, original_name):
    try:
        ext = file_path.split('.')[-1].lower()
        if ext == 'pdf':
            extracted_text = extract_text_from_pdf(file_path)
        elif ext == 'docx':
            extracted_text = extract_text_from_docx(file_path)
        else:
            db.cvs.update_one(
                {'_id': ObjectId(cv_id)},
                {'$set': {'processing_status': 'error', 'error': 'Unsupported file format'}}
            )
            return

        if not extracted_text or len(extracted_text.strip()) < 50:
            db.cvs.update_one(
                {'_id': ObjectId(cv_id)},
                {'$set': {'processing_status': 'error', 'error': 'Insufficient text extracted'}}
            )
            return

        parsed_data = parse_cv_enhanced(extracted_text, file_name=original_name)
        update_fields = parsed_data.copy()

        # ✅ Add raw_text for search and mark as completed
        update_fields.update({
            'processing_status': 'completed',
            'text_length': len(extracted_text),
            'raw_text': extracted_text
        })

        # ✅ Ensure all required fields are present (avoid KeyErrors later)
        for key in [
            'name', 'email', 'phone', 'current_position', 'current_company',
            'total_experience_years', 'total_experience_months', 'batch', 'skills'
        ]:
            if key not in update_fields:
                update_fields[key] = None if key != 'skills' else []

        db.cvs.update_one({'_id': ObjectId(cv_id)}, {'$set': update_fields})

    except Exception as e:
        db.cvs.update_one(
            {'_id': ObjectId(cv_id)},
            {'$set': {'processing_status': 'error', 'error': str(e)}}
        )
