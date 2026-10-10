"""Encrypted transactional outbox, delivered by the worker. No tokens in logs."""
import httpx
import json
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path
from datetime import timedelta

from cryptography.fernet import Fernet
from sqlmodel import Session, select

from app.models.schema import AccountAction, EmailDelivery
from app.services.auth import as_utc, utcnow
from app.settings import get_settings


@lru_cache
def mail_cipher():
    settings = get_settings()
    key = settings.mail_encryption_key
    if not key:
        if settings.production:
            raise RuntimeError('MAIL_ENCRYPTION_KEY is required')
        directory = Path(settings.mail_directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        path = directory / '.key'
        try:
            with path.open('xb') as file:
                os.chmod(path, 0o600)
                file.write(Fernet.generate_key())
        except FileExistsError:
            pass
        key = path.read_bytes()
    return Fernet(key)


def queue_mail(db: Session, owner, subject: str, body: str, expires_at, action_hash: str | None = None):
    payload = json.dumps({'to': owner.email, 'subject': subject, 'body': body, 'action_hash': action_hash}).encode()
    db.add(EmailDelivery(owner_id=owner.id, encrypted_payload=mail_cipher().encrypt(payload).decode(), expires_at=expires_at))


def deliver_pending(db: Session, limit: int = 50, deadline: float | None = None):
    settings = get_settings()
    now = utcnow()
    query = select(EmailDelivery).where(EmailDelivery.next_attempt_at <= now, EmailDelivery.expires_at > now).order_by(EmailDelivery.created_at).limit(limit)
    if db.bind.dialect.name == 'postgresql':
        query = query.with_for_update(skip_locked=True)
    count = 0
    for delivery in db.exec(query).all():
        if deadline is not None and time.monotonic() >= deadline:
            break
        try:
            payload = json.loads(mail_cipher().decrypt(delivery.encrypted_payload.encode()))
            if payload.get('action_hash'):
                action = db.get(AccountAction, payload['action_hash'])
                if action is None or action.used_at or as_utc(action.expires_at) <= now:
                    db.delete(delivery)
                    continue
            message = EmailMessage()
            message['To'] = payload['to']
            message['From'] = settings.smtp_from or 'development@petadvice.invalid'
            message['Subject'] = payload['subject']
            message.set_content(payload['body'])
            if settings.mail_backend == 'file' and not settings.production:
                directory = Path(settings.mail_directory)
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                path = directory / (delivery.id + '.eml')
                with path.open('w') as file:
                    os.chmod(path, 0o600)
                    file.write(message.as_string())
            elif settings.mail_backend == 'resend':
                response = httpx.post('https://api.resend.com/emails',
                    headers={'Authorization': f'Bearer {settings.resend_api_key}', 'Idempotency-Key': f'petadvice/{delivery.id}'},
                    json={'from': settings.smtp_from, 'to': [payload['to']], 'subject': payload['subject'], 'text': payload['body']},
                    # Divide remaining time across connect/write/read/pool phases.
                    timeout=min(10, max(0.1, (deadline-time.monotonic())/4)) if deadline is not None else 10)
                response.raise_for_status()
            elif settings.mail_backend == 'smtp':
                factory = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
                kwargs = {'context': ssl.create_default_context()} if settings.smtp_ssl else {}
                with factory(settings.smtp_host, settings.smtp_port, timeout=15, **kwargs) as smtp:
                    if settings.smtp_starttls and not settings.smtp_ssl:
                        smtp.starttls(context=ssl.create_default_context())
                    if settings.smtp_username:
                        smtp.login(settings.smtp_username, settings.smtp_password)
                    smtp.send_message(message)
            else:
                raise RuntimeError('Unsupported mail backend')
            db.delete(delivery)
            count += 1
        except Exception:
            # Do not log provider errors: they can contain addresses and message bodies.
            delivery.attempts += 1
            delivery.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(delivery.attempts, 7)))
            db.add(delivery)
    db.commit()
    return count
