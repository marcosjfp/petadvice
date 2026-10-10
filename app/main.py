from contextlib import asynccontextmanager
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlmodel import Session

from app.api import jobs, auth, conditions, pets, preventive_care, triage
from app.content.loader import content_library
from app.db import get_session, init_db
from app.jobs.worker import worker_status
from app.services.auth import COOKIE_NAME, clear_session_cookie
from app.services.mail import mail_cipher
from app.services.rate_limit import get_limiter, limit_requests
from app.settings import get_settings

settings = get_settings()
logger = logging.getLogger('petadvice.requests')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production()
    init_db()
    mail_cipher()
    content_library.load()
    yield


app = FastAPI(title='PETAdvice API', version='0.2.0', lifespan=lifespan, dependencies=[Depends(limit_requests('global', '240/minute'))])
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type', 'Authorization', 'X-Guest-Token'])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host.strip() for host in settings.trusted_hosts.split(',') if host.strip()])
for router in [jobs.router, pets.router, auth.router, conditions.router, triage.router, preventive_care.router]:
    app.include_router(router)


@app.exception_handler(StarletteHTTPException)
async def clear_invalid_browser_session(request, error):
    response = await http_exception_handler(request, error)
    if error.status_code == 401 and request.cookies.get(COOKIE_NAME) and not request.headers.get('authorization') and request.scope['path'].removeprefix(request.scope.get('root_path', '')) != '/auth/login':
        clear_session_cookie(response)
    return response


@app.middleware('http')
async def security_headers(request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        # Exception strings, raw URLs, query strings and credentials must not enter logs.
        from starlette.responses import JSONResponse
        response = JSONResponse({'detail': 'An unexpected error occurred. Try again shortly.', 'request_id': request_id}, status_code=500)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if settings.production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    api_path = request.scope['path'].removeprefix(request.scope.get('root_path', ''))
    if api_path.startswith(('/auth', '/pets', '/triage', '/ready', '/privacy', '/jobs')):
        response.headers['Cache-Control'] = 'no-store'
    route = request.scope.get('route')
    logger.info(json.dumps({'event': 'request', 'request_id': request_id, 'method': request.method, 'route': getattr(route, 'path', 'unmatched'), 'status': response.status_code, 'duration_ms': round((time.monotonic() - started) * 1000)}))
    return response


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/ready')
def ready(db: Session = Depends(get_session)):
    try:
        db.execute(text('SELECT 1'))
        init_db()
        if not get_limiter().storage.check():
            raise RuntimeError('Rate-limit store unavailable')
        backlog = worker_status(db)
    except Exception as error:
        raise HTTPException(503, 'Service dependencies are not ready') from error
    if backlog['mail_backlog_delayed']:
        raise HTTPException(503, 'Email delivery is delayed')
    if backlog['worker_stale']:
        raise HTTPException(503, 'Maintenance worker is not ready')
    return {'status': 'ready'}


@app.get('/privacy')
def privacy_notice():
    configured = bool(settings.privacy_operator and settings.privacy_email and settings.privacy_policy_url)
    return {'status': 'configured' if configured else 'draft', 'operator': settings.privacy_operator or None, 'contact': settings.privacy_email or None, 'policy_url': settings.privacy_policy_url or None, 'policy_version': settings.privacy_policy_version, 'guest_retention_hours': settings.guest_retention_hours, 'account_retention': 'Until you delete your account', 'backup_retention': 'Set by the deployment operator; not yet configured' if not configured else 'See the published privacy policy'}
