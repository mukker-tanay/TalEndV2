from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.models.user import UserCreate, UserLogin, AdminUserCreate
from app.utils.auth import hash_password, verify_password, create_access_token, decode_token
from app.db.mongodb import db

router = APIRouter()
users = db.users
security = HTTPBearer()

def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")
    
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
    db_user = users.find_one({"email": user_email})
    if not db_user or db_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return db_user



@router.post("/auth/login")
def login(user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token, 
        "token_type": "bearer",
        "role": db_user.get("role", "user")
    }

@router.get("/auth/admin/users")
def get_all_users(admin_user = Depends(get_current_admin)):
    all_users = users.find({})
    result = []
    for u in all_users:
        result.append({
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role", "user")
        })
    return result

@router.post("/auth/admin/users")
def admin_create_user(user: AdminUserCreate, admin_user = Depends(get_current_admin)):
    if users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    users.insert_one({
        "name": user.name,
        "email": user.email,
        "hashed_password": hash_password(user.password),
        "role": user.role if user.role else "user"
    })
    return {"msg": f"User {user.email} created successfully with role {user.role}"}

class RoleUpdate(BaseModel):
    role: str

@router.put("/auth/admin/users/{email}/role")
def admin_update_role(email: str, role_update: RoleUpdate, admin_user = Depends(get_current_admin)):
    if role_update.role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'admin'")
        
    result = users.update_one(
        {"email": email},
        {"$set": {"role": role_update.role}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"msg": f"User {email} role updated to {role_update.role}"}


