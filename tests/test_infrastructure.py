"""Opt-in real PostgreSQL / Redis tests. Databases are isolated disposable schemas."""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.models.schema import AccountAction, Owner, Pet, TriageSession
from app.services.account_actions import consume_action, token_hash
from app.services.auth import utcnow
from datetime import timedelta
from tests.test_migrations import migrate, seed


@pytest.fixture
def postgres_engine():
    url = os.getenv('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Set TEST_POSTGRES_URL to run PostgreSQL integration tests')
    schema = 'petadvice_test_' + secrets.token_hex(8)
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA {schema}'))
    # Do not include public: an existing public alembic_version could skip the
    # private schema's migrations and redirect unqualified test writes there.
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def test_postgres_migrations_and_foreign_keys(postgres_engine):
    from sqlalchemy.exc import IntegrityError
    migrate(postgres_engine); migrate(postgres_engine)
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = current_schema() AND table_name IN ('owner','pet','triagesession')")).scalar() == 3
    seed(postgres_engine)
    with Session(postgres_engine) as db:
        assert db.get(Pet, 'pet').name == 'Rex'
        with pytest.raises(IntegrityError):
            db.execute(text("INSERT INTO pet (id,owner_id,name,species) VALUES ('bad','missing','No owner','dog')"))
        db.rollback()
        assert db.get(TriageSession, 'check').pet_id == 'pet'


def test_postgres_reset_link_is_claimed_once_under_concurrency(postgres_engine):
    from fastapi import HTTPException
    migrate(postgres_engine)
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = 'accountaction'")).scalar() == 1
    seed(postgres_engine)
    token = secrets.token_urlsafe(32)
    with Session(postgres_engine) as db:
        db.add(AccountAction(token_hash=token_hash(token), owner_id='owner', kind='reset', expires_at=utcnow() + timedelta(minutes=30)))
        db.commit()
    def claim(_):
        with Session(postgres_engine) as db:
            try:
                consume_action(db, token, 'reset'); db.commit()
                return True
            except HTTPException:
                return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(claim, range(4))) == 1


def test_redis_limits_are_shared_across_instances():
    from limits import parse
    from limits.storage import storage_from_string
    from limits.strategies import FixedWindowRateLimiter
    url = os.getenv('TEST_REDIS_URL')
    if not url:
        pytest.skip('Set TEST_REDIS_URL to run Redis integration tests')
    first = FixedWindowRateLimiter(storage_from_string(url))
    second = FixedWindowRateLimiter(storage_from_string(url))
    scope = secrets.token_hex(16)
    budget = parse('2/minute')
    assert first.hit(budget, scope)
    assert second.hit(budget, scope)
    assert not first.hit(budget, scope)
    assert first.storage.check() and second.storage.check()
    first.clear(budget, scope)
