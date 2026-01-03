
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/cvtool")

client = MongoClient(MONGO_URI, server_api=ServerApi('1'))

db = client["cvtool"]  

try:
    client.admin.command("ping")
    print("Connected to MongoDB Atlas from mongodb.py")
except Exception as e:
    print("MongoDB connection failed:", e)
