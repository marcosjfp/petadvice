#!/bin/sh
set -eu
# This runs once on an EMPTY PostgreSQL volume. Application credentials are not superuser credentials.
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 --set app_password="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE petadvice_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'app_password') \gexec
CREATE DATABASE petadvice OWNER petadvice_app;
REVOKE ALL ON DATABASE petadvice FROM PUBLIC;
SQL
