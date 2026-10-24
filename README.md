# PETAdvice

PETAdvice is a React/TypeScript and FastAPI app for dog and cat symptom urgency checks, preventive-care information and saved pet history. It provides educational guidance, not a diagnosis. The beta's clinical content is still awaiting veterinary review.

## Live tester beta

**Try the app: [petadvice.vercel.app](https://petadvice.vercel.app)** — no Vercel account is required.

- Guest symptom checks, Learn and Care are available without signing up.
- Test accounts support password login, pet profiles, saved checks and account data controls.
- **Email verification and password recovery are disabled in this beta.** Keep your test password; the app cannot send a reset link.
- Use test email addresses, fictional pet details and a password you do not use elsewhere. The full privacy policy and operator/contact setup remain unfinished.

The beta runs on Vercel, Supabase PostgreSQL and Upstash Redis/QStash. Deployment previews remain behind Vercel authentication. See the [cloud setup notes](docs/operations/vercel-supabase-setup.md) for the current configuration and [release guide](docs/vercel-release.md) for full-release requirements.

## Features

- Guest checks with branching questions, urgency guidance, private access tokens, expiry, download and deletion.
- Argon2id password hashes, HttpOnly/SameSite cookies, revocable sessions and logout across devices. Normal HTTPS production deployments use Secure cookies.
- Email verification and single-use password recovery for fully configured deployments; these features are disabled in the live tester beta.
- Public Learn and Care pages for dogs and cats, including symptom search and life-stage information.
- Multiple pet profiles and private, paginated check history.
- Results with recorded answers, explanations of existing urgency rules, sources and preserved report context.
- Printable/PDF and downloadable HTML summaries. Saved checks retain the guidance recorded at the time instead of recalculating it from current content.
- Password confirmation for account export, deletion and session controls.
- PostgreSQL/Alembic migrations, shared Redis rate limits, encrypted mail outbox and retention/readiness monitoring.
- Responsive phone layouts, locally hosted fonts and a PWA shell. Symptom checks require an online API; private API responses are not cached for offline use.

Scheduled care reminders and editing previously submitted answers are not implemented.

## Phone layout and app updates

The phone layout includes larger form controls, constrained date/select fields, wrapping headers and report text, and safe-area spacing. The emergency reminder follows the content on small screens so it does not cover controls; desktop retains the fixed reminder.

The layout was checked at iPhone 15 portrait/landscape dimensions, smaller phone widths and desktop sizes using Chrome. Physical iPhone/Safari keyboard, date-picker and safe-area behavior still needs device verification. See the [mobile verification report and screenshots](docs/verification/mobile-2026-10-24/README.md).

An existing PWA installation can retain an older interface after a deployment. Refresh PETAdvice; if it still looks old, close its tabs or saved app and reopen it. Account data does not need to be deleted.

## Local development

Use Python 3.13 or 3.14 and Node 24. CI, Vercel and the API container use Python 3.14.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
# Create local defaults without overwriting an existing configuration.
cp -n .env.example .env
# Back up an existing database before applying migrations.
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In separate terminals, also from the repository root:

```sh
# Write development emails locally and clean up expired data.
.venv/bin/python -m app.jobs.worker
```

```sh
npm ci --prefix web
npm run dev --prefix web -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the backend on port 8000. Keep the frontend hostname consistent when testing cookie login. Local API docs are at `http://127.0.0.1:8000/docs`.

Settings load the ignored root `.env`; `.env.example` documents local options. Set a stable random `JWT_SECRET_KEY` there if development sessions should survive API restarts. Development mail is written to private `.mail/*.eml` files and is not sent externally. Those files contain account-action links and must stay private.

SQLite is supported for local development. Startup checks migration readiness and refuses pending migrations; it does not create or alter tables automatically. The current migration head is `0005`.

## Deployment and configuration

For Vercel, use the repository root, the FastAPI framework and `server:app`. The build command is `python scripts/build_vercel.py`; it installs locked frontend dependencies and copies Vite output into `public/` without migrating the database. Keep the `public/**` function inclusion in `vercel.json` so the generated frontend and navigation fallback are available at runtime. Use [`.env.vercel.example`](.env.vercel.example) and the [Vercel release guide](docs/vercel-release.md).

| Mode | Configuration | Account/email behavior |
| --- | --- | --- |
| Normal deployment | Preview/beta flags unset or false | Verification and recovery require configured email delivery in production |
| Private guest preview | `GUEST_ONLY_PREVIEW=true`, Vercel Preview only | Guest checks; account endpoints disabled |
| Private account preview | `ACCOUNTS_WITHOUT_EMAIL_PREVIEW=true`, Vercel Preview only | Test accounts; verification/recovery disabled |
| Main-domain tester beta | `ACCOUNTS_WITHOUT_EMAIL_BETA=true`, Vercel Production only | Test accounts; verification/recovery disabled |

Choose at most one preview/beta mode. Cloud deployments use `APP_ENV=production` and `DEPLOYMENT_MODE=scheduled`; QStash runs signed maintenance callbacks. Email-disabled modes install only the maintenance schedule. Normal email-enabled deployments also need mail reconciliation. Review or apply schedules with `scripts/configure_jobs.py` as described in the release guide.

For self-hosted containers, use [`compose.yaml`](compose.yaml) and the [operations runbook](docs/operations/runbook.md). That setup uses Caddy, PostgreSQL, Redis, a one-off migration service, the API and a separate worker.

Normal production requires a restricted PostgreSQL role, shared Redis, stable secrets, exact HTTPS origins/hosts, SMTP/TLS or Resend delivery, an operator/privacy contact and a published policy. The explicitly enabled tester beta is a separate exception to email and completed-policy checks, not a completed full release. Its test resources are currently shared with the private preview; isolate real production data before leaving the beta.

Guest access expires after 24 hours by default and scheduled cleanup removes expired checks. Accounts remain until deletion. Backup/log retention and restored-deletion handling still need operator decisions. Notice acknowledgement records a policy version; technical controls alone do not establish compliance. The [privacy-policy draft](docs/privacy-policy-draft.md) remains unpublished.

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

Backend tests isolate their databases; migration/restore tests use temporary files. Set `TEST_POSTGRES_URL` and `TEST_REDIS_URL` for infrastructure tests, which use disposable schemas and unique rate-limit keys. Set `TEST_APP_URL=http://127.0.0.1:8080/api` only for an isolated development deployment: HTTP smoke tests create and remove their own synthetic data. Do not point the general test suite at a public production service.

The latest local checks passed 93 backend tests (6 infrastructure tests skipped), 14 frontend tests, frontend lint and the TypeScript/Vite/PWA build. CI also runs PostgreSQL/Redis integration tests, migration checks and dependency audits; see [the Checks workflow](.github/workflows/checks.yml).

Python dependencies are locked in hashed `requirements.txt` and in `pyproject.toml`/`uv.lock` for Vercel. Keep those definitions aligned. Frontend dependencies use `web/package-lock.json`; container images are pinned to digests.

## Repository guide

| Path | Purpose |
| --- | --- |
| `web/` | React UI, styles, PWA configuration and frontend tests |
| `app/` | FastAPI endpoints, authentication, content, data models and background jobs |
| `server.py` | Vercel entrypoint, `/api` mount and frontend fallback |
| `migrations/` | Versioned Alembic database changes |
| `scripts/` | Build, scheduling, import, backup, restore and probe helpers |
| `deploy/` | Container images, Caddy and database setup |
| `docs/` | Release/operations guides, implementation review and verification evidence |

The [implementation review](docs/modernization-review.md) records the broader modernization work. Clinical question/content files and escalation rules were preserved during the deployment and mobile-layout corrections.

Environment files, `.vercel/` credentials, mail, backups, generated frontend output and databases are ignored. The original database was removed from current Git tracking, but older Git history still contains that file; history has not been rewritten.
