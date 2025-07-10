# backend/app/db/mongodb.py

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Get URI from environment variable
MONGO_URI = os.getenv("MONGODB_URI")

# Initialize the client
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))

# Connect to your specific database
db = client["cvtool"]  # change if your DB has a different name

# Optional: test the connection once when module is loaded
try:
    client.admin.command("ping")
    print("✅ Connected to MongoDB Atlas from mongodb.py")
except Exception as e:
    print("❌ MongoDB connection failed:", e)
