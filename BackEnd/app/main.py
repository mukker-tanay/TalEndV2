import os
import sentry_sdk
from fastapi import FastAPI
from app.api import auth, upload, search
from fastapi.middleware.cors import CORSMiddleware

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,
    environment=os.getenv("ENVIRONMENT", "production"),
)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(search.router)

ALLOWED_ORIGINS = [
    "https://jobnoc.com",
    "https://www.jobnoc.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
