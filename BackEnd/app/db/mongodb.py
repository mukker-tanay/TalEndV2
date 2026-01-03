
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

# Only load .env if MONGODB_URI is not already set
if not os.getenv("MONGODB_URI"):
    load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/cvtool")

print(f"Connecting to MongoDB at: {MONGO_URI}") # Debug print

client = MongoClient(MONGO_URI, server_api=ServerApi('1'))

db = client["cvtool"]  

try:
    client.admin.command("ping")
    print("Connected to MongoDB Atlas from mongodb.py")
except Exception as e:
    print("MongoDB connection failed:", e)
