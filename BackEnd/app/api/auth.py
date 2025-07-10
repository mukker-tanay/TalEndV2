from fastapi import APIRouter, HTTPException
from app.models.user import UserCreate, UserLogin
from app.utils.auth import hash_password, verify_password, create_access_token
from app.db.mongodb import db

router = APIRouter()
users = db.users

@router.post("/auth/register")
def register(user: UserCreate):
    if users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    users.insert_one({
        "email": user.email,
        "hashed_password": hash_password(user.password)
    })
    return {"msg": "User registered successfully"}

@router.post("/auth/login")
def login(user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}
