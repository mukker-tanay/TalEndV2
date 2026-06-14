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

@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(search.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For testing; restrict in prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
