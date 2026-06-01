from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    name: str                
    email: EmailStr
    password: str

class AdminUserCreate(BaseModel):
    name: str                
    email: EmailStr
    role: Optional[str] = "user"

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
