# PETAdvice

PETAdvice combines React/TypeScript and FastAPI for dog/cat symptom urgency and preventive-care information. Its questions were tailored with veterinary input. Educational guidance does not replace examination by a vet; this modernization pass preserves the clinical question/content files.

## Features

- Guest checks with branching questions, urgency guidance, private access tokens, expiry, download and deletion.
- Cookie login, Argon2id passwords, email verification, single-use recovery links, revocable sessions and logout across devices.
- Pet profiles/switching, searchable condition details, sources and life-stage care information.
- Password confirmation for account export/deletion and session controls.
- PostgreSQL/Alembic, shared Redis rate limits, encrypted mail outbox, retention worker and readiness monitoring.
- Same-origin container deployment with Caddy, a non-root API/worker, local font assets and PWA shell. Checks need an online API; reminders/history editing are future product work.

Read the [implementation review](docs/modernization-review.md), [operations runbook](docs/operations/runbook.md) and [unpublished privacy-policy draft](docs/privacy-policy-draft.md).

## Native development

Python 3.13 works locally; the container/CI target Python 3.14. Use Node 24.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
# Preserve an existing database backup before migrating it.
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In separate terminals:

```sh
.venv/bin/python -m app.jobs.worker
npm ci --prefix web
npm run dev --prefix web -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the backend. Keep the same frontend hostname for cookie tests. API docs are at `http://127.0.0.1:8000/docs`. Settings load an ignored root `.env` if present; `.env.example` explains configuration. Development emails are private `.mail/*.eml` files, delivered by the worker, with no external sending.

The application checks the Alembic schema at startup and refuses pending migrations. It no longer creates/rewrites tables during startup. SQLite remains available for native development; production requires PostgreSQL and shared Redis. Fresh container installations separate database administrator and restricted application roles.

## Deployment and privacy

Use `compose.yaml` and the [runbook](docs/operations/runbook.md) for local containers, PostgreSQL import, encrypted backups/restores, retention and rollback. The old ephemeral backend-only Render manifest has been retired. Choose hosting, domain and SMTP before remote deployment; no provider has been selected or deployed.

Production requires stable keys, exact HTTPS origins/hosts, SMTP/TLS, a restricted database role, operator/contact and a published policy URL. Verification is mandatory in production. Browser tokens use one-hour HttpOnly/SameSite cookies; mutations validate trusted origins. Tokens are checked against stored sessions, so logout/password reset revoke access. API clients may use Bearer tokens with the same revocation rules.

Guest access expires after 24 hours by default, with configurable scheduled cleanup. Accounts are retained until deletion. Backup/log retention and restored-deletion handling need an operator decision before launch. Account notice acknowledgement records the policy version; technical controls do not establish legal compliance.

The supplied local preview now uses the restricted `petadvice_app` database login for the API, worker and migrations. The explicitly approved transition preserved existing records and administrator access. Production refuses administrator app credentials.

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m alembic check
npm run lint --prefix web
npm test --prefix web
npm run build --prefix web
npm audit --prefix web
uvx pip-audit -r requirements.txt --disable-pip
```

API tests isolate their database. Migration/restore tests use temporary files. Set `TEST_POSTGRES_URL` and `TEST_REDIS_URL` for real infrastructure tests; these use disposable schemas and unique rate-limit keys. Set `TEST_APP_URL=http://127.0.0.1:8080/api` only for an isolated development deployment; HTTP smoke tests create and remove their own synthetic data. Never point smoke tests at a public production service.

CI runs PostgreSQL/Redis integration tests alongside backend tests and migrations, plus frontend lint/tests/build/advisories. Hashed Python and npm lockfiles record tested dependencies. Base/service images are pinned to tested digests; update them with verification for security patches.

## Repository data

The working `petadvice.db` was privately backed up, migrated and removed from current Git tracking. Environment files, mailboxes, backups and databases are ignored and excluded from container builds. Older Git history still contains the original database; history was not rewritten. Review that history before publishing the repository.
