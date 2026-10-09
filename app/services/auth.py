"""Password hashing, revocable sessions and browser authentication."""
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import AuthSession, Owner
from app.settings import get_settings

SECRET_KEY = get_settings().jwt_secret_key
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60
COOKIE_NAME = 'petadvice_session'
_password_hash = PasswordHash.recommended()
_dummy_hash = _password_hash.hash(secrets.token_urlsafe(32))
_bearer_scheme = HTTPBearer(auto_error=False)


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def validate_auth_configuration():
    # Kept independently callable for authentication configuration checks.
    if os.getenv('APP_ENV', 'development') == 'production':
        configured = os.getenv('JWT_SECRET_KEY', '')
        if len(configured) < 32 or configured == 'dev-only-insecure-secret-change-me':
            raise RuntimeError('Production requires a random JWT_SECRET_KEY of at least 32 characters')
        origins = os.getenv('CORS_ORIGINS', '').split(',')
        if not origins or any(not origin.strip().startswith('https://') or '*' in origin for origin in origins):
            raise RuntimeError('Production requires explicit HTTPS CORS_ORIGINS')


def hash_password(password: str):
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    try:
        if hashed_password.startswith(('$2a$', '$2b$', '$2y$')):
            return len(plain_password.encode()) <= 72 and bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        return _password_hash.verify(plain_password, hashed_password)
    except (ValueError, UnknownHashError):
        return False


def verify_dummy_password(password: str):
    _password_hash.verify(password, _dummy_hash)


def set_session_cookie(response: Response, token: str):
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=get_settings().production, samesite='lax', max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path='/')


def clear_session_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='lax', secure=get_settings().production)


def allowed_origins():
    return set(get_settings().origins)


def verify_auth_origin(request: Request):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = request.headers.get('origin')
        if (origin is not None and origin not in allowed_origins()) or (origin is None and request.headers.get('sec-fetch-site') == 'cross-site'):
            raise HTTPException(403, 'Request origin is not allowed')


def create_access_token(owner_id: str, session_id: str | None = None):
    now = utcnow()
    return jwt.encode({'sub': owner_id, 'jti': session_id or secrets.token_hex(16), 'exp': now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), 'iat': now, 'iss': 'petadvice', 'aud': 'petadvice-api'}, SECRET_KEY, algorithm=ALGORITHM)


def decode_claims(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], issuer='petadvice', audience='petadvice-api', options={'require': ['sub', 'jti', 'exp', 'iat', 'iss', 'aud']})
        if not all(isinstance(payload.get(k), str) and payload[k] for k in ['sub', 'jti']):
            raise jwt.InvalidTokenError('Missing subject or session')
        return payload
    except jwt.PyJWTError as error:
        raise HTTPException(401, 'Invalid or expired session', headers={'WWW-Authenticate': 'Bearer'}) from error


def decode_access_token(token: str):
    return decode_claims(token)['sub']


def issue_session(db: Session, owner: Owner):
    session = AuthSession(owner_id=owner.id, expires_at=utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    db.add(session)
    db.commit()
    db.refresh(session)
    return create_access_token(owner.id, session.id)


def find_session(db: Session, token: str):
    claims = decode_claims(token)
    session = db.get(AuthSession, claims['jti'])
    if session is None or session.owner_id != claims['sub'] or session.revoked_at or as_utc(session.expires_at) <= utcnow():
        raise HTTPException(401, 'Invalid or expired session', headers={'WWW-Authenticate': 'Bearer'})
    return session


def revoke_all_sessions(db: Session, owner_id: str):
    for session in db.exec(select(AuthSession).where(AuthSession.owner_id == owner_id, AuthSession.revoked_at.is_(None))).all():
        session.revoked_at = utcnow()
        db.add(session)


def get_optional_owner(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme), db: Session = Depends(get_session)):
    token = credentials.credentials if credentials else request.cookies.get(COOKIE_NAME)
    if token is None:
        return None
    if credentials is None and request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.headers.get('origin') not in allowed_origins():
        raise HTTPException(403, 'Request origin is not allowed')
    session = find_session(db, token)
    owner = db.get(Owner, session.owner_id)
    if owner is None:
        raise HTTPException(401, 'Invalid or expired session')
    request.state.auth_session = session
    return owner


def get_current_owner(owner: Owner | None = Depends(get_optional_owner)):
    if owner is None:
        raise HTTPException(401, 'Not authenticated', headers={'WWW-Authenticate': 'Bearer'})
    return owner


def require_verified_owner(owner: Owner = Depends(get_current_owner)):
    if get_settings().email_verification_required and owner.email_verified_at is None:
        raise HTTPException(403, 'Verify your email before saving pet profiles or starting account checks')
    return owner


def require_recent_owner(request: Request, owner: Owner = Depends(get_current_owner)):
    if as_utc(request.state.auth_session.authenticated_at) < utcnow() - timedelta(minutes=10):
        raise HTTPException(403, 'Confirm your password before this sensitive action')
    return owner
