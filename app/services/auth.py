"""Password hashing and JWT authentication for owner accounts."""
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlmodel import Session

from app.db import get_session
from app.models.schema import Owner

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(48)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
COOKIE_NAME = "petadvice_session"
_password_hash = PasswordHash.recommended()
_dummy_hash = _password_hash.hash(secrets.token_urlsafe(32))
_bearer_scheme = HTTPBearer(auto_error=False)


def validate_auth_configuration() -> None:
    if os.getenv("APP_ENV", "development") == "production":
        configured = os.getenv("JWT_SECRET_KEY", "")
        if len(configured) < 32 or configured == "dev-only-insecure-secret-change-me":
            raise RuntimeError("Production requires a random JWT_SECRET_KEY of at least 32 characters")
        origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
        if not origins or any(not origin.startswith("https://") or "*" in origin for origin in origins):
            raise RuntimeError("Production requires explicit HTTPS CORS_ORIGINS")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            # Legacy bcrypt accounts remain usable and are upgraded after login.
            if len(plain_password.encode()) > 72:
                return False
            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        return _password_hash.verify(plain_password, hashed_password)
    except (ValueError, UnknownHashError):
        return False


def verify_dummy_password(password: str) -> None:
    _password_hash.verify(password, _dummy_hash)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=os.getenv("APP_ENV") == "production",
        samesite="lax", max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax",
                           secure=os.getenv("APP_ENV") == "production")


def allowed_origins() -> set[str]:
    origins = {origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
    ).split(",") if origin.strip()}
    return origins


def verify_auth_origin(request: Request) -> None:
    # Protect login/logout as well as authenticated mutations from browser CSRF.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if (origin is not None and origin not in allowed_origins()) or (
            origin is None and request.headers.get("sec-fetch-site") == "cross-site"
        ):
            raise HTTPException(status_code=403, detail="Request origin is not allowed")


def create_access_token(owner_id: str) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": owner_id, "exp": expires_at, "iat": now,
                       "iss": "petadvice", "aud": "petadvice-api"}, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],
                             issuer="petadvice", audience="petadvice-api",
                             options={"require": ["sub", "exp", "iat", "iss", "aud"]})
        owner_id = payload.get("sub")
        if not isinstance(owner_id, str) or not owner_id:
            raise jwt.InvalidTokenError("Missing subject")
        return owner_id
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def get_optional_owner(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_session),
) -> Owner | None:
    token = credentials.credentials if credentials else request.cookies.get(COOKIE_NAME)
    if token is None:
        return None
    if credentials is None and request.method not in {"GET", "HEAD", "OPTIONS"}:
        # SameSite alone is not a CSRF defense against sibling subdomains.
        if request.headers.get("origin") not in allowed_origins():
            raise HTTPException(status_code=403, detail="Request origin is not allowed")
    owner_id = decode_access_token(token)
    owner = db.get(Owner, owner_id)
    if owner is None:
        raise HTTPException(status_code=401, detail="Owner not found")
    return owner


def get_current_owner(owner: Owner | None = Depends(get_optional_owner)) -> Owner:
    if owner is None:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return owner
