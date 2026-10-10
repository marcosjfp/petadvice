"""Bounded, signed serverless jobs. No tokens or email bodies in scheduler data."""
import base64
import hashlib
import hmac
import time
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.db import get_session
from app.jobs.cleanup import cleanup
from app.models.schema import EmailDelivery, MaintenanceStatus
from app.services.auth import utcnow
from app.services.mail import deliver_pending
from app.settings import get_settings

router = APIRouter(prefix='/jobs', tags=['jobs'])


async def verify_job(request: Request):
    settings = get_settings()
    if settings.deployment_mode != 'scheduled':
        raise HTTPException(404, 'Not found')
    signature = request.headers.get('Upstash-Signature', '')
    if not signature or len(signature) > 4096:
        raise HTTPException(401, 'Invalid job signature')
    body = await request.body()
    if len(body) > 1024:
        raise HTTPException(413, 'Job request too large')
    digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')
    for key in (settings.qstash_current_signing_key, settings.qstash_next_signing_key):
        if not key:
            continue
        try:
            claims = jwt.decode(signature, key, algorithms=['HS256'], issuer='Upstash',
                options={'require': ['iss', 'sub', 'exp', 'nbf', 'body']})
            if claims['sub'] == settings.job_callback_url and isinstance(claims['body'], str) and hmac.compare_digest(claims['body'].rstrip('='), digest):
                return
        except jwt.InvalidTokenError:
            pass
    raise HTTPException(401, 'Invalid job signature')


class JobRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['mail', 'maintenance']


@router.post('/run', dependencies=[Depends(verify_job)])
def run_job(body: JobRequest, db: Session = Depends(get_session)):
    # Duplicate callbacks are safe: locks skip in-flight outbox rows; Resend
    # uses a stable idempotency key. Cleanup only removes expired records.
    if body.kind == 'mail':
        delivered = deliver_pending(db, limit=3, deadline=time.monotonic()+40)
        pending = db.exec(select(EmailDelivery.id).where(EmailDelivery.expires_at > utcnow()).limit(1)).first()
        if pending:
            # Keep scheduler retries active, including deferred provider retries.
            raise HTTPException(503, 'Email work remains; retry this job', headers={'Retry-After': '60'})
        return {'status': 'ok', 'delivered': delivered}
    counts = cleanup(db, apply=True, limit=200)
    # A full batch may leave more expired data; retry before claiming freshness.
    if any(counts[name] >= 200 for name in ('guest_checks', 'auth_sessions', 'account_links', 'queued_emails')):
        raise HTTPException(503, 'Retention work remains; retry this job', headers={'Retry-After': '60'})
    db.merge(MaintenanceStatus(job='maintenance', last_success_at=utcnow()))
    db.commit()
    return {'status': 'ok', **counts}
