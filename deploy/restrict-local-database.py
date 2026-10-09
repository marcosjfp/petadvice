"""Prepare/apply the restricted app role in this task's isolated local database.
Apply only with explicit authorization. This preview's transition was approved and
completed on 2026-10-09; do not reapply it to the existing database.
Dry run is the default. No extra administrator is created. Existing app data is preserved.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess

from dotenv import dotenv_values

TABLES = ['owner', 'pet', 'triagesession', 'authsession', 'accountaction', 'emaildelivery', 'guestaccess', 'maintenancestatus', 'alembic_version']
CONTAINER = 'petadvice-modernization-db-1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps({'container': CONTAINER, 'database': 'petadvice', 'role': 'petadvice_app', 'superuser': False, 'can_create_databases': False, 'can_create_roles': False, 'ownership_scope': ['petadvice database', 'public schema', *TABLES], 'administrator_unchanged': True, 'apply': args.apply}))
    if not args.apply:
        return
    path = Path('.env.local')
    values = dict(dotenv_values(path))
    password = secrets.token_hex(32)
    sql = "CREATE ROLE petadvice_app LOGIN PASSWORD '" + password + "' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; ALTER DATABASE petadvice OWNER TO petadvice_app; ALTER SCHEMA public OWNER TO petadvice_app;"
    for table in TABLES:
        sql += ' ALTER TABLE IF EXISTS public.' + table + ' OWNER TO petadvice_app;'
    result = subprocess.run(['docker', 'exec', '-i', CONTAINER, 'psql', '-U', 'petadvice', '-d', 'petadvice', '-v', 'ON_ERROR_STOP=1', '-1'], input=sql, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        raise SystemExit('Restricted role update failed. Existing environment was retained.')
    values['DATABASE_URL'] = 'postgresql+psycopg://petadvice_app:' + password + '@db:5432/petadvice'
    values['POSTGRES_PASSWORD'] = password
    path.write_text('\n'.join(k + '=' + v for k, v in values.items()) + '\n')
    os.chmod(path, 0o600)
    print('Application role configured. Restart the local app containers to use it.')


if __name__ == '__main__':
    main()
