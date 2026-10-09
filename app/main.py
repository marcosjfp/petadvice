from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, conditions, pets, preventive_care, triage
from app.content.loader import content_library
from app.db import init_db
from app.services.auth import COOKIE_NAME, clear_session_cookie, validate_auth_configuration


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_configuration()
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(pets.router)
app.include_router(auth.router)
app.include_router(conditions.router)
app.include_router(triage.router)
app.include_router(preventive_care.router)


@app.exception_handler(StarletteHTTPException)
async def clear_invalid_browser_session(request, error):
    response = await http_exception_handler(request, error)
    if (error.status_code == 401 and request.cookies.get(COOKIE_NAME)
            and not request.headers.get("authorization") and request.url.path != "/auth/login"):
        # Expired/restarted sessions must not prevent a signed-out guest check.
        clear_session_cookie(response)
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith(("/auth", "/pets", "/triage")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    return {"status": "ok"}
