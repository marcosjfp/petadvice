"""Deliver the outbox and enforce retention. Run one worker per deployment."""
import argparse
import json
import time
from datetime import timedelta

from sqlmodel import Session, select

from app.db import engine, init_db
from app.jobs.cleanup import cleanup
from app.models.schema import EmailDelivery, MaintenanceStatus
from app.services.auth import as_utc, utcnow
from app.services.mail import deliver_pending, mail_cipher
from app.settings import get_settings


def worker_status(db: Session):
    delayed = db.exec(select(EmailDelivery).where(EmailDelivery.created_at < utcnow() - timedelta(minutes=10), EmailDelivery.expires_at > utcnow())).first()
    heartbeat = db.get(MaintenanceStatus, 'maintenance')
    return {'mail_backlog_delayed': delayed is not None, 'worker_stale': heartbeat is None or as_utc(heartbeat.last_success_at) < utcnow() - timedelta(minutes=2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    get_settings().validate_production()
    init_db()
    mail_cipher()
    while True:
        with Session(engine) as db:
            sent = deliver_pending(db)
            counts = cleanup(db, apply=True)
            db.merge(MaintenanceStatus(job='maintenance', last_success_at=utcnow()))
            db.commit()
            print(json.dumps({'event': 'maintenance', 'mail_delivered': sent, **counts, **worker_status(db)}), flush=True)
        if args.once:
            break
        time.sleep(30)


if __name__ == '__main__':
    main()
