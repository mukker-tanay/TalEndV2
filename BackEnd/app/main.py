from fastapi import FastAPI
from app.api import auth, upload, search
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(search.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For testing; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
