"""Copy a migrated SQLite snapshot into empty, migrated PostgreSQL in one transaction.
Live sessions, recovery links and queued mail are deliberately invalidated by cutover.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func
from sqlmodel import Session, create_engine, select
from app.db import migration_config, normalize_database_url
from app.models.schema import AccountAction, AuthSession, EmailDelivery, GuestAccess, Owner, Pet, TriageSession
from app.settings import get_settings


def import_snapshot(source: Path, target_url: str, dry_run=False):
    if not source.is_file():
        raise RuntimeError('Source snapshot does not exist')
    src = create_engine(f'sqlite:///file:{source.resolve()}?mode=ro&uri=true')
    target_url = normalize_database_url(target_url)
    if not target_url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Import destination must be PostgreSQL')
    dst = create_engine(target_url)
    heads = set(ScriptDirectory.from_config(migration_config()).get_heads())
    try:
        for engine in [src, dst]:
            with engine.connect() as connection:
                if set(MigrationContext.configure(connection).get_current_heads()) != heads:
                    raise RuntimeError('Migrate both databases before importing')
        counts = {}
        with Session(src) as source_db, Session(dst) as target_db:
            for model in [Owner, Pet, TriageSession, AuthSession, AccountAction, EmailDelivery, GuestAccess]:
                if target_db.exec(select(func.count()).select_from(model)).one():
                    raise RuntimeError('Destination is not empty; import refused')
            for model in [Owner, Pet, TriageSession]:
                rows = source_db.exec(select(model)).all()
                counts[model.__tablename__] = len(rows)
                if not dry_run:
                    for row in rows:
                        target_db.add(model.model_validate(row.model_dump()))
                    target_db.flush()
                    if target_db.exec(select(func.count()).select_from(model)).one() != len(rows):
                        raise RuntimeError('Import count verification failed')
            if not dry_run:
                target_db.commit()
        return {'applied': not dry_run, 'records': counts, 'active_credentials_migrated': False}
    finally:
        src.dispose(); dst.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Apply import; default is a dry run')
    args = parser.parse_args()
    try:
        print(import_snapshot(args.source, get_settings().database_url, dry_run=not args.apply))
    except Exception as error:
        print(f'Import failed ({type(error).__name__}). Check migrated snapshot and empty PostgreSQL destination.', file=sys.stderr)
        sys.exit(1)
