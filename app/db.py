from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import event, text
from sqlmodel import Session, create_engine

from app.settings import get_settings


def normalize_database_url(url: str) -> str:
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg://', 1)
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return url


DATABASE_URL = normalize_database_url(get_settings().database_url)
connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {'options': '-c timezone=UTC'}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def enable_sqlite_constraints(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')


def migration_config() -> Config:
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / 'alembic.ini'))
    config.set_main_option('script_location', str(root / 'migrations'))
    return config


def init_db() -> None:
    """Check schema readiness. Deployments apply migrations before starting workers."""
    scripts = ScriptDirectory.from_config(migration_config())
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_heads()
        if get_settings().production and engine.dialect.name == 'postgresql':
            privileged = connection.execute(text('SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname = current_user')).scalar()
            if privileged:
                raise RuntimeError('Production database credentials must use a non-administrator application role')
    if set(current) != set(scripts.get_heads()):
        raise RuntimeError('Database migrations are pending. Back up the database, then run: python -m alembic upgrade head')


def get_session():
    with Session(engine) as session:
        yield session
