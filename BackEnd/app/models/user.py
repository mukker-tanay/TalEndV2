from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    name: str                
    email: EmailStr
    password: str

class AdminUserCreate(UserCreate):
    role: Optional[str] = "user"

class UserLogin(BaseModel):
    email: EmailStr
    password: str
