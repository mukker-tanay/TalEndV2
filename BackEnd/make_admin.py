import sys
import os

# Add BackEnd directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.mongodb import db
from app.utils.auth import hash_password

email = "tanaymukker@gmail.com"

user = db.users.find_one({"email": email})

if not user:
    db.users.insert_one({
        "name": "Tanay Mukker",
        "email": email,
        "hashed_password": hash_password("Admin@123"),
        "role": "admin"
    })
    print(f"User {email} created with role admin. Default password is: Admin@123")
else:
    db.users.update_one({"email": email}, {"$set": {"role": "admin"}})
    print(f"User {email} upgraded to admin.")
