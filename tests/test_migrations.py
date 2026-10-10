from pathlib import Path

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlmodel import Session, select

from app.db import migration_config
from app.models.schema import Owner, Pet, TriageSession


def migrate(engine, revision='head'):
    with engine.begin() as connection:
        config = migration_config()
        config.attributes['connection'] = connection
        command.upgrade(config, revision)


def seed(engine):
    with engine.begin() as db:
        db.execute(text("INSERT INTO owner (id,email,hashed_password,created_at) VALUES ('owner','seed@example.com','not-a-real-password-hash','2026-01-01 00:00:00')"))
        db.execute(text("INSERT INTO pet (id,owner_id,name,species,environment_factors,known_conditions) VALUES ('pet','owner','Rex','dog','[]','[]')"))
        db.execute(text("INSERT INTO triagesession (id,pet_id,started_at,symptom_entry_point,answers_json,current_question_id,condition_entries_matched_raw) VALUES ('check','pet','2026-01-01 00:00:00','vomiting','{}','q-vomit-001','')"))


def test_fresh_schema_is_versioned_and_idempotent(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "fresh.sqlite3"}')
    migrate(engine); migrate(engine)
    with engine.connect() as db:
        assert MigrationContext.configure(db).get_current_revision() == '0004'
        assert db.execute(text('PRAGMA foreign_key_check')).all() == []
    assert {'owner', 'pet', 'triagesession', 'authsession', 'guestaccess', 'emaildelivery', 'accountaction'} <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_legacy_pet_table_and_check_links_are_recovered(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "legacy.sqlite3"}')
    migrate(engine, '0001'); seed(engine)
    with engine.begin() as db:
        db.execute(text('ALTER TABLE pet RENAME TO pet_legacy'))
        metadata = MetaData()
        Table('owner', metadata, autoload_with=db)
        legacy = Table('pet_legacy', metadata, autoload_with=db)
        replacement = legacy.to_metadata(metadata, name='pet')
        replacement.indexes.clear()
        replacement.create(db)
        db.execute(text('DROP TABLE alembic_version'))
    migrate(engine)
    assert 'pet_legacy' not in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(Pet, 'pet').name == 'Rex'
        assert db.get(TriageSession, 'check').pet_id == 'pet'
        assert db.get(Owner, 'owner').email == 'seed@example.com'
        assert db.execute(text('PRAGMA foreign_key_check')).all() == []
        assert inspect(engine).get_foreign_keys('triagesession')[0]['referred_table'] == 'pet'
    engine.dispose()


def test_encrypted_backup_restore_and_tamper_detection(tmp_path, monkeypatch):
    import sys
    from cryptography.fernet import Fernet
    from app.settings import get_settings
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    from backup_database import backup
    from restore_database import restore
    source = tmp_path / 'source.sqlite3'
    engine = create_engine(f'sqlite:///{source}')
    migrate(engine); seed(engine); engine.dispose()
    monkeypatch.setattr(get_settings(), 'database_url', f'sqlite:///{source}')
    monkeypatch.setenv('BACKUP_ENCRYPTION_KEY', Fernet.generate_key().decode())
    encrypted = tmp_path / 'database.pab'
    assert backup(encrypted)['encrypted'] is True
    assert b'seed@example.com' not in encrypted.read_bytes()
    restored = tmp_path / 'restored.sqlite3'
    assert restore(encrypted, f'sqlite:///{restored}')['restored'] is True
    restored_engine = create_engine(f'sqlite:///{restored}')
    with Session(restored_engine) as db:
        assert db.get(Pet, 'pet').name == 'Rex'
    restored_engine.dispose()
    with pytest.raises(RuntimeError):
        restore(encrypted, f'sqlite:///{restored}')
    corrupted = tmp_path / 'corrupt.pab'
    data = bytearray(encrypted.read_bytes()); data[50] ^= 1; corrupted.write_bytes(data)
    destination = tmp_path / 'bad.sqlite3'
    with pytest.raises(Exception):
        restore(corrupted, f'sqlite:///{destination}')
    assert not destination.exists()


def test_report_upgrade_preserves_preexisting_results(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "old-results.sqlite3"}')
    migrate(engine, '0003'); seed(engine)
    with engine.begin() as db:
        db.execute(text("UPDATE triagesession SET current_question_id=NULL, resulting_urgency='vet_soon', resulting_guidance='Original saved advice', condition_entries_matched_raw='old-condition' WHERE id='check'"))
    migrate(engine)
    with Session(engine) as db:
        check = db.get(TriageSession, 'check')
        assert check.result_snapshot is None
        assert check.resulting_guidance == 'Original saved advice'
        assert check.condition_entries_matched_raw == 'old-condition'
        assert check.pet_id == 'pet'
    assert 'ix_triagesession_pet_started_id' in {index['name'] for index in inspect(engine).get_indexes('triagesession')}
    engine.dispose()
