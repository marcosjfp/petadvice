"""Shared abuse controls. Production never falls back to process-local storage."""
import hashlib
import hmac
import os
from ipaddress import ip_address
import time
from functools import lru_cache

from fastapi import HTTPException, Request
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter
from starlette.concurrency import run_in_threadpool

from app.settings import get_settings


@lru_cache
def get_limiter():
    uri = get_settings().rate_limit_storage_uri
    options = {'socket_connect_timeout': 2, 'socket_timeout': 2} if uri.startswith(('redis://', 'rediss://')) else {}
    return FixedWindowRateLimiter(storage_from_string(uri, **options))


def check_limit(scope: str, identity: str, budget: str):
    digest = hmac.new(get_settings().jwt_secret_key.encode(), identity.encode(), hashlib.sha256).hexdigest()
    try:
        limiter = get_limiter()
        item = parse(budget)
        allowed = limiter.hit(item, 'petadvice', scope, digest)
        retry_after = max(1, int(limiter.get_window_stats(item, 'petadvice', scope, digest).reset_time - time.time()) + 1) if not allowed else 0
    except Exception as error:
        raise HTTPException(503, 'Request protection is temporarily unavailable. Try again shortly.') from error
    if not allowed:
        raise HTTPException(429, 'Too many requests. Please try again later.', headers={'Retry-After': str(retry_after)})


def client_identity(request: Request) -> str:
    # Trust the platform-overwritten header only inside the Vercel runtime.
    # Self-hosted deployments continue to use Uvicorn's configured proxy trust.
    if os.environ.get('VERCEL') == '1':
        forwarded = request.headers.get('x-vercel-forwarded-for', '')
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client else 'unknown'


def limit_requests(scope: str, budget: str, email_budget: str | None = None):
    async def dependency(request: Request):
        # Uvicorn accepts forwarded addresses only from the explicitly configured proxy.
        await run_in_threadpool(check_limit, scope, client_identity(request), budget)
        if email_budget:
            try:
                body = await request.json()
            except ValueError:
                return
            email = body.get('email') if isinstance(body, dict) else None
            if isinstance(email, str):
                await run_in_threadpool(check_limit, scope + '-identity', email.strip().lower(), email_budget)
    return dependency
