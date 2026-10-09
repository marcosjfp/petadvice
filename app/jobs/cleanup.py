"""Retention jobs. Only expired guest data and security records are removed."""
import argparse
import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import or_
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models.schema import AccountAction, AuthSession, EmailDelivery, GuestAccess, Pet, TriageSession
from app.services.auth import utcnow
from app.settings import get_settings


def cleanup(db: Session, apply: bool = False):
    now = utcnow()
    cutoff = now - timedelta(hours=get_settings().guest_retention_hours)
    expired = db.exec(select(TriageSession).join(Pet).outerjoin(GuestAccess, GuestAccess.session_id == TriageSession.id).where(
        Pet.owner_id.is_(None),
        or_(GuestAccess.expires_at <= now, GuestAccess.session_id.is_(None) & (TriageSession.started_at <= cutoff)),
    )).all()
    counts = {'guest_checks': len(expired), 'auth_sessions': 0, 'account_links': 0, 'queued_emails': 0, 'development_emails': 0}
    for check in expired:
        if apply:
            access = db.get(GuestAccess, check.id)
            if access:
                db.delete(access)
                db.flush()
            db.delete(check)
    if apply:
        db.flush()
        # A guest pet is an ephemeral wrapper for one check, not a saved profile.
        has_check = select(TriageSession.id).where(TriageSession.pet_id == Pet.id).exists()
        for pet in db.exec(select(Pet).where(Pet.owner_id.is_(None), ~has_check)).all():
            db.delete(pet)
    for model, name, predicate in [
        (AuthSession, 'auth_sessions', (AuthSession.expires_at <= now - timedelta(days=1)) | (AuthSession.revoked_at <= now - timedelta(days=1))),
        (AccountAction, 'account_links', (AccountAction.expires_at <= now) | AccountAction.used_at.is_not(None)),
        (EmailDelivery, 'queued_emails', EmailDelivery.expires_at <= now),
    ]:
        records = db.exec(select(model).where(predicate)).all()
        counts[name] = len(records)
        if apply:
            for record in records:
                db.delete(record)
    if not get_settings().production and get_settings().mail_backend == 'file':
        for file in Path(get_settings().mail_directory).glob('*.eml'):
            if file.stat().st_mtime < now.timestamp() - 86400:
                counts['development_emails'] += 1
                if apply:
                    file.unlink()
    if apply:
        db.commit()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Delete expired records; default is a dry run')
    args = parser.parse_args()
    init_db()
    with Session(engine) as db:
        print(json.dumps({'applied': args.apply, **cleanup(db, apply=args.apply)}))


if __name__ == '__main__':
    main()
