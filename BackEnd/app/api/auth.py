import secrets
import string
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models.user import (
    UserCreate,
    UserLogin,
    AdminUserCreate,
    PasswordChange,
    DisableUpdate,
)
from app.utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)
from app.db.mongodb import db

limiter = Limiter(key_func=get_remote_address)


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%" for c in pwd)
        ):
            return pwd


router = APIRouter()
users = db.users
security = HTTPBearer()


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    if not user_email:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )

    db_user = users.find_one({"email": user_email})
    if not db_user or db_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return db_user


@router.post("/auth/login")
@limiter.limit("10/minute")
def login(request: Request, user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if db_user.get("disabled", False):
        raise HTTPException(
            status_code=403, detail="Account disabled. Contact your administrator."
        )

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": db_user.get("role", "user"),
        "require_password_change": db_user.get("must_change_password", False),
    }


@router.post("/auth/change-password")
def change_password(
    passwords: PasswordChange,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    user_data = decode_token(token)
    user_email = user_data.get("sub")

    if not user_email:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )

    db_user = users.find_one({"email": user_email})
    if not db_user or not verify_password(
        passwords.old_password, db_user["hashed_password"]
    ):
        raise HTTPException(status_code=401, detail="Invalid old password")

    users.update_one(
        {"email": user_email},
        {
            "$set": {
                "hashed_password": hash_password(passwords.new_password),
                "must_change_password": False,
            }
        },
    )
    return {"msg": "Password updated successfully"}


@router.get("/auth/admin/users")
def get_all_users(admin_user=Depends(get_current_admin)):
    all_users = users.find({})
    result = []
    for u in all_users:
        result.append(
            {
                "name": u.get("name"),
                "email": u.get("email"),
                "role": u.get("role", "user"),
            }
        )
    return result


@router.post("/auth/admin/users")
def admin_create_user(user: AdminUserCreate, admin_user=Depends(get_current_admin)):
    if users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    temp_password = generate_temp_password()
    users.insert_one(
        {
            "name": user.name,
            "email": user.email,
            "hashed_password": hash_password(temp_password),
            "role": user.role if user.role else "user",
            "must_change_password": True,
        }
    )
    return {
        "msg": f"User {user.email} created successfully with role {user.role}",
        "temp_password": temp_password,
    }


class RoleUpdate(BaseModel):
    role: str


@router.put("/auth/admin/users/{email}/role")
def admin_update_role(
    email: str, role_update: RoleUpdate, admin_user=Depends(get_current_admin)
):
    if role_update.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=400, detail="Invalid role. Must be 'user' or 'admin'"
        )

    result = users.update_one({"email": email}, {"$set": {"role": role_update.role}})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"msg": f"User {email} role updated to {role_update.role}"}


@router.post("/auth/admin/users/{email}/reset-password")
def admin_reset_password(email: str, admin_user=Depends(get_current_admin)):
    if email == admin_user["email"]:
        raise HTTPException(
            status_code=400, detail="Cannot perform this action on your own account."
        )

    target_user = users.find_one({"email": email})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = generate_temp_password()
    users.update_one(
        {"email": email},
        {
            "$set": {
                "hashed_password": hash_password(temp_password),
                "must_change_password": True,
            }
        },
    )
    return {"msg": f"Password reset for {email}", "temp_password": temp_password}


@router.put("/auth/admin/users/{email}/disable")
def admin_set_disabled(
    email: str, update: DisableUpdate, admin_user=Depends(get_current_admin)
):
    if email == admin_user["email"]:
        raise HTTPException(
            status_code=400, detail="Cannot perform this action on your own account."
        )

    result = users.update_one({"email": email}, {"$set": {"disabled": update.disabled}})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"msg": f"User {email} {'disabled' if update.disabled else 'enabled'}"}
