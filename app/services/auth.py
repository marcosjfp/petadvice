"""Password hashing and JWT authentication for owner accounts."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.db import get_session
from app.models.schema import Owner

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(owner_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": owner_id, "exp": expires_at}, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        owner_id = payload.get("sub")
        if not isinstance(owner_id, str):
            raise jwt.InvalidTokenError("Missing subject")
        return owner_id
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from error


def get_current_owner(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_session),
) -> Owner:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    owner_id = decode_access_token(credentials.credentials)
    owner = db.get(Owner, owner_id)
    if owner is None:
        raise HTTPException(status_code=401, detail="Owner not found")
    return owner


def get_optional_owner(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_session),
) -> Owner | None:
    if credentials is None:
        return None
    owner_id = decode_access_token(credentials.credentials)
    owner = db.get(Owner, owner_id)
    if owner is None:
        raise HTTPException(status_code=401, detail="Owner not found")
    return owner
