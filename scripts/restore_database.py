"""Restore into a NEW, empty database. Existing data is never overwritten."""
import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from app.db import normalize_database_url
from backup_database import MAGIC, key_bytes, pg_command


def unpack(source: Path, target: Path):
    with source.open('rb') as src, target.open('xb') as dst:
        os.chmod(target, 0o600)
        prefix = src.read(len(MAGIC))
        if prefix != MAGIC:
            dst.write(prefix)
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
            return
        key = key_bytes()
        if not key:
            raise RuntimeError('An encryption key is required for this backup')
        nonce = src.read(12)
        src.seek(-16, 2)
        tag = src.read(16)
        end = src.tell() - 16
        src.seek(len(MAGIC) + 12)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        while src.tell() < end:
            dst.write(decryptor.update(src.read(min(1024 * 1024, end - src.tell()))))
        dst.write(decryptor.finalize())  # Authentication must succeed before any restore is attempted.


def restore(source: Path, target_url: str, container=None):
    url = make_url(normalize_database_url(target_url))
    if url.get_backend_name() == 'sqlite' and Path(url.database).exists():
        raise RuntimeError('SQLite destination exists; choose a new path')
    if url.get_backend_name() == 'postgresql':
        engine = create_engine(url)
        try:
            if inspect(engine).get_table_names():
                raise RuntimeError('Destination PostgreSQL database is not empty')
        finally:
            engine.dispose()
    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary) / 'database'
        unpack(source, raw)
        if url.get_backend_name() == 'sqlite':
            db = sqlite3.connect(raw)
            try:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                    raise RuntimeError('Backup integrity/foreign-key check failed')
            finally:
                db.close()
            destination = Path(url.database)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with raw.open('rb') as src, destination.open('xb') as dst:
                os.chmod(destination, 0o600)
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
        elif url.get_backend_name() == 'postgresql':
            command, env = pg_command('pg_restore', url, container)
            with raw.open('rb') as file:
                result = subprocess.run(command + ['--exit-on-error', '--single-transaction', '--no-owner', '--no-acl', '--dbname', url.database], env=env, stdin=file, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError('pg_restore failed; the transaction was rolled back')
        else:
            raise RuntimeError('Only SQLite and PostgreSQL are supported')
    return {'restored': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--container', help='Optional local PostgreSQL container to run pg_restore in')
    args = parser.parse_args()
    try:
        target = os.environ['RESTORE_DATABASE_URL']
        print(restore(args.backup, target, args.container))
    except Exception as error:
        print(f'Restore failed ({type(error).__name__}). Check backup, key and empty destination.', file=sys.stderr)
        sys.exit(1)
