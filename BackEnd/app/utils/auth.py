import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError


# 🔑 Load environment variables from .env file
load_dotenv()

# ✅ Define JWT_SECRET from environment
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

# ❗Fail early if it's not set
if not JWT_SECRET:
    raise ValueError("JWT_SECRET is not set in the environment variables")

# ✅ Password hashing config
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def create_access_token(data: dict, expires_minutes=30):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return {}
