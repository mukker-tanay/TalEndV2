from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo import ASCENDING, DESCENDING, TEXT
from dotenv import load_dotenv
import os

if not os.getenv("MONGODB_URI"):
    load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/cvtool")

client = MongoClient(
    MONGO_URI,
    server_api=ServerApi('1'),
    maxPoolSize=20,
    minPoolSize=2,
)

db = client["cvtool"]

try:
    client.admin.command("ping")
except Exception as e:
    print("MongoDB connection failed:", e)


def ensure_indexes():
    cvs = db.cvs
    cvs.create_index("processing_status")
    cvs.create_index("user_email")
    cvs.create_index("upload_time")
    cvs.create_index("graduation_batch")
    cvs.create_index("tags")
    cvs.create_index("total_experience_years")
    cvs.create_index([("email", ASCENDING), ("user_email", ASCENDING)])
    cvs.create_index([("phone", ASCENDING), ("user_email", ASCENDING)])
    cvs.create_index([("raw_text", TEXT)], default_language="english")


ensure_indexes()
