"""Consistent database backups, optionally encrypted with a separate 32-byte key."""
import argparse
import base64
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy.engine import make_url
from app.db import normalize_database_url
from app.settings import get_settings

MAGIC = b'PETADVICE-BACKUP-v1\n'


def key_bytes():
    key = os.getenv('BACKUP_ENCRYPTION_KEY', '') or get_settings().backup_encryption_key
    if not key:
        if get_settings().production:
            raise RuntimeError('Production backups require a separate BACKUP_ENCRYPTION_KEY')
        return None
    try:
        result = base64.urlsafe_b64decode(key)
        if len(result) != 32:
            raise ValueError()
        return result
    except ValueError as error:
        raise RuntimeError('BACKUP_ENCRYPTION_KEY must be a URL-safe base64 encoded 32-byte key') from error


def pg_command(tool, url, container=None):
    env = os.environ.copy()
    env.update(PGDATABASE=url.database or '', PGUSER=url.username or '', PGPASSWORD=url.password or '')
    if container:
        cmd = ['docker', 'exec', '-i', '-e', 'PGDATABASE', '-e', 'PGUSER', '-e', 'PGPASSWORD', container, tool]
    else:
        env.update(PGHOST=url.host or 'localhost', PGPORT=str(url.port or 5432))
        # Preserve libpq TLS parameters instead of silently dropping URL query settings.
        for parameter, variable in [('sslmode', 'PGSSLMODE'), ('sslrootcert', 'PGSSLROOTCERT'), ('sslcert', 'PGSSLCERT'), ('sslkey', 'PGSSLKEY')]:
            if parameter in url.query:
                env[variable] = url.query[parameter]
        cmd = [tool]
    return cmd, env


def encrypt_file(source, target, key):
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    with open(source, 'rb') as src, open(target, 'xb') as dst:
        os.chmod(target, 0o600)
        dst.write(MAGIC + nonce)
        while chunk := src.read(1024 * 1024):
            dst.write(encryptor.update(chunk))
        dst.write(encryptor.finalize() + encryptor.tag)


def backup(output: Path, container=None):
    url = make_url(normalize_database_url(get_settings().database_url))
    if output.exists():
        raise RuntimeError('Backup destination already exists; choose a new filename')
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = key_bytes()
    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary) / 'database'
        if url.get_backend_name() == 'sqlite':
            source = sqlite3.connect(Path(url.database).resolve().as_uri() + '?mode=ro', uri=True)
            target = sqlite3.connect(raw)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('SQLite backup integrity check failed')
            finally:
                source.close(); target.close()
        elif url.get_backend_name() == 'postgresql':
            command, env = pg_command('pg_dump', url, container)
            with raw.open('wb') as file:
                result = subprocess.run(command + ['--format=custom', '--no-owner', '--no-acl'], env=env, stdout=file, stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError('pg_dump failed; check server/client compatibility and credentials')
        else:
            raise RuntimeError('Only SQLite and PostgreSQL are supported')
        os.chmod(raw, 0o600)
        if key:
            encrypt_file(raw, output, key)
        else:
            with raw.open('rb') as src, output.open('xb') as dst:
                os.chmod(output, 0o600)
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
    return {'encrypted': bool(key), 'bytes': output.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--container', help='Optional local PostgreSQL container to run pg_dump in')
    args = parser.parse_args()
    try:
        print(backup(args.output, args.container))
    except Exception as error:
        # Never print database driver/provider errors, which can include private data.
        print(f'Backup failed ({type(error).__name__}). Check configuration and destination.', file=sys.stderr)
        sys.exit(1)
