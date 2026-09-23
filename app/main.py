from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conditions, pets, preventive_care, triage
from app.content.loader import content_library
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    content_library.load()
    yield


app = FastAPI(title="PETAdvice API", version="0.1.0", lifespan=lifespan)
cors_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(pets.router)
app.include_router(conditions.router)
app.include_router(triage.router)
app.include_router(preventive_care.router)


@app.get("/health")
def health():
    return {"status": "ok"}
