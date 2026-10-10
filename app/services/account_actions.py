import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select

from app.models.schema import AccountAction, Owner
from app.services.auth import utcnow
from app.services.mail import queue_mail
from app.jobs.dispatch import trigger_mail
from app.settings import get_settings


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def request_action(db: Session, owner: Owner, kind: str):
    # Serialize resends with login/reset on the same owner in PostgreSQL.
    owner = db.exec(select(Owner).where(Owner.id == owner.id).with_for_update()).one()
    now = utcnow()
    # Supersede outstanding links; there is only one usable action of each kind.
    for action in db.exec(select(AccountAction).where(AccountAction.owner_id == owner.id, AccountAction.kind == kind, AccountAction.used_at.is_(None))).all():
        action.used_at = now
        db.add(action)
    token = secrets.token_urlsafe(32)
    expires = now + (timedelta(minutes=30) if kind == 'reset' else timedelta(hours=24))
    db.add(AccountAction(token_hash=token_hash(token), owner_id=owner.id, kind=kind, expires_at=expires))
    # Fragments never enter HTTP request URLs, proxy access logs or referrers.
    link = get_settings().public_web_url.rstrip('/') + '/#' + urlencode({'action': kind, 'token': token})
    title = 'Reset your PETAdvice password' if kind == 'reset' else 'Verify your PETAdvice email'
    body = f'{title}:\n\n{link}\n\nThis link expires in {"30 minutes" if kind == "reset" else "24 hours"}. If you did not request it, ignore this email.'
    queue_mail(db, owner, title, body, expires, action_hash=token_hash(token))
    db.commit()
    trigger_mail()


def consume_action(db: Session, token: str, kind: str):
    now = utcnow()
    digest = token_hash(token)
    action = db.get(AccountAction, digest)
    owner = db.exec(select(Owner).where(Owner.id == action.owner_id).with_for_update()).first() if action else None
    if owner is None:
        db.rollback()
        raise HTTPException(400, 'This link is invalid or expired. Request a new link.')
    # A conditional UPDATE serializes competing submissions in SQLite and PostgreSQL.
    claimed = db.execute(update(AccountAction).where(AccountAction.token_hash == digest, AccountAction.kind == kind, AccountAction.used_at.is_(None), AccountAction.expires_at > now).values(used_at=now).execution_options(synchronize_session=False)).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(400, 'This link is invalid or expired. Request a new link.')
    return owner
