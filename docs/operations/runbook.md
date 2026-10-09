# PETAdvice operations and release runbook

This repository now supports versioned PostgreSQL deployments, shared Redis protection, a maintenance worker and same-origin browser access. No remote provider, domain or SMTP account has been selected or deployed.

## Local native development

Install the hashed Python requirements and run `npm ci` in `web`. Back up an existing SQLite database before migrating it. Then:

```sh
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --no-access-log
# Separate terminal: deliver local .mail/*.eml files and enforce retention
.venv/bin/python -m app.jobs.worker
# Separate terminal, from web/
npm run dev
```

The development mail backend writes only private `.mail/*.eml` files. It sends no external email. Do not share these files: they contain verification/recovery links. Production requires SMTP with TLS and a valid, separately generated `MAIL_ENCRYPTION_KEY`. Protect that key; rotating it requires draining/re-encrypting the pending outbox first.

A random process-local development JWT secret signs users out on restart. Configure a stable secret to retain development sessions. Never use the old public secret. Each API process must use the same stable secret when sharing Redis/session records.

## Container topology

`compose.yaml` provides PostgreSQL 18, Redis 8, a one-off migration service, API, worker and Caddy/static frontend. API and database ports are not published. Caddy strips `/api` before proxying, keeping browser cookies on the same origin. Default HTTP binding is loopback port 8080 for local use. Set the real domain and ports explicitly for HTTPS public hosting.

The API/worker run as a non-root user with a read-only root filesystem. The database network is internal in the deployment file. API/worker have a separate network for SMTP egress. Caddy has a fixed, configurable private address; Uvicorn trusts forwarded client addresses only from that address. Change `PROXY_IP` and `PROXY_SUBNET` together if they conflict with your host networks.

The fresh-volume initializer creates a restricted `petadvice_app` role with ownership of its application database; the bootstrap `petadvice` administrator uses a separate password. Production startup refuses administrator application credentials. Never expose database/Redis ports publicly. Managed databases should use a restricted application role and verified TLS as appropriate for the provider.

### Current isolated local preview

The private `.env.local` was generated during this implementation. The preview project is named `petadvice-modernization`, at `http://127.0.0.1:8080`. On 2026-10-09, the user explicitly approved the one-time transition in `deploy/restrict-local-database.py`, which has been applied. The API, worker and migrations now use `petadvice_app`, which owns the application database, public schema and application tables but has no superuser, database-creation, role-creation, replication or row-security-bypass privileges. Existing records and administrator authentication were preserved; `.env.local` remains mode 600. Both services passed the production database-role check, readiness was healthy, and all 69 backend tests passed using the restricted credentials. The preview remains in development mode pending production configuration.

The transition script is a one-time tool for this existing isolated database; do not reapply it. Fresh volumes use the automatic restricted-role initializer instead. Its dry run describes the access changes without applying them.

```sh
# Local testing only. This override publishes DB/Redis ports to loopback.
docker compose --env-file .env.local -p petadvice-modernization \
  -f compose.yaml -f deploy/compose.test.yaml up -d --build
# Keep data while stopping the preview:
docker compose --env-file .env.local -p petadvice-modernization \
  -f compose.yaml -f deploy/compose.test.yaml stop
```

Never use the test override for public hosting. Never use `down -v` on data you want to preserve.

## First production release

1. Choose the domain, hosting region, database/backup provider and SMTP provider. Complete and approve `docs/privacy-policy-draft.md`, including backup/log retention and restore deletion handling.
2. Populate an ignored `.env` or secret store using `.env.example`. Generate independent database administrator/application passwords, a stable JWT secret, a Fernet mail key, and a separate backup encryption key. Do not put secrets in build arguments, source code or command-line URLs. Percent-encode special characters in database URL passwords, or use generated hexadecimal passwords.
3. Set `APP_ENV=production`, exact HTTPS browser origins, `PUBLIC_WEB_URL`, explicit trusted hosts (include localhost for health checks), provider SMTP/TLS settings, operator/contact/policy URL, and shared Redis. Verification is mandatory in production, regardless of the development flag.
4. Configure Caddy's `SITE_ADDRESS`, public port bindings and DNS, and confirm certificate issuance. Configure storage encryption, provider access controls and automated backup expiry. The repository does not configure provider storage encryption or publish DNS.
5. Back up, apply migrations once, then start API/worker/frontend. The API never creates/alters tables on startup; it refuses pending migrations. Review generated migrations before applying them. Only a migration process should apply schema changes, never multiple concurrent replicas.
6. Probe `/api/ready`, check maintenance heartbeat and test signup, verification, recovery and deletion with synthetic accounts. Schedule external uptime/error alerts and email failure alerts to a chosen operator destination; none has been connected yet.

Production logs must keep Uvicorn access logging disabled. Raw access URLs can expose IDs and query strings. The supplied Caddyfile does not enable access logging. If a provider/CDN adds it, configure minimization and retention explicitly.

## SQLite-to-PostgreSQL cutover

1. Stop writes to SQLite and take a consistent snapshot. Preserve the original and encryption keys privately.
2. Apply Alembic migrations to the snapshot using `DATABASE_URL=sqlite:///ABSOLUTE_SNAPSHOT_PATH`. Revision `0001` adopts the beta schema and recovers records from the old `pet_legacy` table. Conflicting/orphaned records stop the migration; reconcile them without deleting source records.
3. Create an **empty** PostgreSQL destination and run `alembic upgrade head` there. Set `DATABASE_URL` to that destination in a private environment.
4. Run `python scripts/import_sqlite.py --source /absolute/snapshot.sqlite3` for a dry run, then the same command with `--apply`. The import checks schema heads, refuses existing destination records and verifies account/profile/check counts in one transaction. It intentionally does not migrate live sessions, recovery/verification links or pending mail: users sign in and request fresh links after cutover.
5. Verify records and restored-backup behavior, switch the application configuration, and retain the old snapshot only for the operator-approved rollback window. Do not run both systems accepting writes.

The implementation tested a copy of the actual local beta: one account, one recovered pet and one check were preserved. Clinical questions/content files were not changed.

## Backups and restoration

`pg_dump`/`pg_restore` must match the server major version; use the database container's binaries for the supplied local setup. Both tools keep credentials out of command arguments and suppress potentially private provider errors. Native use requires suitable PostgreSQL client tools. Use private files/directories and a separately stored `BACKUP_ENCRYPTION_KEY` for production. The tools use streaming AES-256-GCM encryption, authenticated before restoration.

```sh
# DATABASE_URL and BACKUP_ENCRYPTION_KEY come from a private environment.
python scripts/backup_database.py --output .backups/RELEASE-TIMESTAMP.pab
# For local Docker instead of installed PostgreSQL clients:
python scripts/backup_database.py --output .backups/RELEASE-TIMESTAMP.pab \
  --container petadvice-modernization-db-1

# RESTORE_DATABASE_URL points at a NEW empty database/path.
python scripts/restore_database.py --backup .backups/RELEASE-TIMESTAMP.pab
# Optional --container uses that container's pg_restore.
```

Existing SQLite paths or nonempty PostgreSQL targets are refused. PostgreSQL restoration is one transaction, without `--clean` or ownership reassignment. Corrupt/wrong-key encrypted backups are rejected before database restoration. Test restores regularly and measure recovery time; a successful backup alone does not establish recoverability. The encrypted PostgreSQL restore drill passed locally and restored matching records; its temporary databases were removed.

There is no installed production backup schedule or off-host destination yet. Define frequency, retention, encryption/key recovery, access control and expiry after choosing hosting. Keep backup keys separate from backup files. Reapply deletions before a restored database is reopened to users; choose a deletion ledger/process and its retention before launch.

## Retention and maintenance

```sh
python -m app.jobs.cleanup          # report only
python -m app.jobs.cleanup --apply  # remove expired data
python -m app.jobs.worker --once    # deliver eligible mail, clean up, update heartbeat
```

The worker runs every 30 seconds. Default guest access/retention is 24 hours, configurable from 1–720 hours. Expired guest capabilities are rejected immediately, even if cleanup is delayed. Account profiles/checks remain until deletion; no automatic inactivity deletion is installed. Sessions expire after one hour; expired/revoked session records are cleaned after one day. Used/expired action links and expired outbox entries are cleared; development emails expire after a day. Backups are independent and need an operator schedule.

Mail delivery is at least once: a crash after SMTP accepted a message but before commit can cause a duplicate email. Links are single use, and superseded/used links are skipped. SMTP failures retry with bounded backoff until expiry. Run one maintenance worker in this deployment; PostgreSQL outbox row locks also prevent simultaneous delivery by cooperating workers.

## Monitoring and rollback

- `/health`: process liveness. `/ready`: database connectivity/schema head, Redis availability, maintenance heartbeat under two minutes old, and no eligible email backlog over ten minutes. A stopped worker causes readiness failure even without queued email.
- `python scripts/probe.py --url https://YOUR_DOMAIN/api/ready` returns nonzero on failure and logs only status/duration. Connect this to the hosting monitor and an approved alert destination.
- Structured application request logs include route templates, status, timing and random request IDs. Use 5xx rate/latency and readiness as operational signals. No external metrics/alert account is configured.
- Release images should have immutable tags/digests and a recorded previous release. Do not use a floating `local` tag for production rollback. The Docker base/service images are pinned to the locally tested digests; review and refresh them with tests for security updates.
- For a code-only rollback with a compatible schema, restart API/worker/web with the previous immutable image tag and verify readiness. Do not automatically run Alembic downgrade. For incompatible/destructive schema changes, stop writes and restore a verified backup into a new database, reapply deletions, then switch configuration. Account for any writes after the backup.

A local encrypted restore drill and restart/recovery using recorded, verified image tags were performed during this pass. There is no prior production release; compatibility with a real previous release, remote rollback, HTTPS/DNS, SMTP delivery and operator alerts remain deployment work.

## Repository data

`petadvice.db` is removed from the current Git index, while the working database and a private pre-migration backup remain locally. `.mail`, `.backups`, environment files and database files are ignored and excluded from container build context. Older Git commits still contain the original database. History was not rewritten; assess that history before publishing the repository and rotate any real exposed credentials if applicable.

## Primary references

- [Alembic migration tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [SQLite batch migrations](https://alembic.sqlalchemy.org/en/latest/batch.html).
- [PostgreSQL backup/restore](https://www.postgresql.org/docs/current/backup-dump.html).
- [OWASP recovery](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
- [Shared limits storage](https://limits.readthedocs.io/en/stable/storage.html).
