# PETAdvice Vercel release

Prepared 2026-10-10. Enhancements 1–4 are implemented: public Learn/Care, rule-based result explanations, printable/downloadable reports, and private pet history. The clinical content/question files and escalation decisions are preserved. No reviewer attribution was added. No provider resources or public deployment have been created.

## Architecture

| Service | Purpose | Application configuration |
| --- | --- | --- |
| Vercel | Vite static frontend and FastAPI function on one HTTPS origin | Root project, FastAPI framework, `server.py` |
| Neon PostgreSQL | Profiles, checks, sessions, encrypted email outbox | Restricted role; pooled TLS `DATABASE_URL` |
| Upstash Redis | Shared request protection | TCP/TLS `rediss://` URL, not a REST endpoint |
| Resend | Verification and recovery email | HTTPS API key and verified sending domain |
| Upstash QStash | Immediate email wakeups, retries and scheduled reconciliation/retention | Token plus current/next signing keys |

[Vercel's FastAPI documentation](https://vercel.com/docs/frameworks/backend/fastapi) supports the explicit entrypoint, custom build command and root `public/` CDN directory used here. The function mounts the API at `/api`; existing Docker/native entrypoints remain available. Build installs the locked frontend dependencies and copies Vite output to `public/`. It does not connect to or migrate a database. Runtime validates production configuration and schema readiness. Python 3.14 is specified in `.python-version`; use Node 24 in Project Settings. Enable [access to system environment variables](https://vercel.com/docs/environment-variables/system-environment-variables) so the runtime can identify Vercel and its trusted headers. Cloud startup also refuses development mode or the local worker configuration.

The shared API gets `no-store` headers, and the service worker never caches API responses. Static security headers are defined in `vercel.json`. Provider-forwarded IPs are used for abuse limits only inside Vercel's runtime, using its [platform request header](https://vercel.com/docs/headers/request-headers); self-hosted deployments retain their existing proxy trust rules.

## 1. Create isolated provider resources

Create a Vercel project from a private repository with **repository root** as Root Directory and **FastAPI** as Framework Preset. Use `python scripts/build_vercel.py` as Build Command, leaving Output Directory at the framework default. Do not select the `web` directory: it would omit the backend. Choose function/database/Redis regions close to one another. The Vercel project can use a free `vercel.app` address initially.

Create separate preview and production databases, Redis databases, Resend keys and QStash credentials/accounts where practical. Do not point temporary branch previews at production. Use a fixed preview alias for exact origins, hostnames and the signed callback destination; unconfigured ephemeral URLs will intentionally fail host/origin checks. Protect previews. QStash requires a reachable endpoint: configure [Vercel's automation bypass secret](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation) if protection is enabled (`VERCEL_AUTOMATION_BYPASS_SECRET`); triggers and schedule setup forward it in a private, redacted header. Do not put bypass secrets in the callback URL, browser code, or Git. Verify that ordinary preview access remains protected.

For Neon, use a dedicated `petadvice_app` login with no superuser, create-role, create-database, replication or bypass-RLS permissions. Give it access/ownership only within the application's database/schema, so it can apply migrations. Do not use a provider administrator connection as `DATABASE_URL`. Startup rejects privileged app roles. Use the provider's pooled hostname for request traffic with TLS. Scheduled mode uses no persistent local SQLAlchemy pool, disables prepared statements and sets UTC per transaction to support transaction pooling. Follow [Neon's pooling guidance](https://neon.com/docs/connect/connection-pooling).

Create Upstash Redis and copy its **Redis TCP connection URI** including TLS and credentials. Resend requires a verified sending domain for mail to real users; a hosting subdomain alone does not supply that sender identity. See [Resend's domain instructions](https://resend.com/docs/dashboard/domains/introduction).

## 2. Configure private environment variables

Use [`.env.vercel.example`](../.env.vercel.example) as the reference. Enter real values in Vercel's Preview/Production Environment Variables, scoped separately. Do not upload `.env.local` or paste secrets into issue/PR bodies. Never expose backend secrets through `VITE_` variables. The browser uses same-origin `/api` without a custom API URL.

Generate a stable random `JWT_SECRET_KEY` and an independent Fernet `MAIL_ENCRYPTION_KEY`. Keep the backup encryption key separately in the backup environment. Rotating the JWT secret invalidates sessions; losing the mail key makes pending encrypted messages unreadable. Back up the mail key with your recovery material.

Set `APP_ENV=production`, `DEPLOYMENT_MODE=scheduled`, `MAIL_BACKEND=resend`, `RESEND_API_KEY`, `SMTP_FROM`, the pooled `DATABASE_URL`, Redis URI and all QStash credentials. `QSTASH_URL` must match the region of the QStash account. Set `PUBLIC_WEB_URL` to the exact clean HTTPS origin, `CORS_ORIGINS` to exact allowed HTTPS origins, and `TRUSTED_HOSTS` to their hostname(s), with no wildcards. Callback signatures are checked against `${PUBLIC_WEB_URL}/api/jobs/run`.

Operator name, privacy email, published privacy-policy URL/version and backup/log retention remain undecided. Complete the existing [privacy draft](privacy-policy-draft.md) with the actual hosting/providers and retention practices before public release; production startup refuses missing operator/contact/policy configuration. A URL must point to a real published policy. Do not mark placeholder text as a completed policy.

## 3. Prepare the database before directing traffic

Use a private migration environment with the direct TLS URL for the same restricted app role as `DIRECT_DATABASE_URL`. It overrides the pooled runtime URL for Alembic only; avoid including it in the deployed function environment. Migrate a new preview database first:

```sh
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
```

Head is `0004`: it adds nullable JSON report snapshots and a history pagination index. Existing checks/relationships remain intact. Old saved urgency/guidance is preserved; missing historical context and explanations are not reconstructed from today's content. New reports freeze on their first result retrieval, when the app displays the guidance. Incomplete checks appear in history but cannot provide a completed report.

If keeping existing local data, privately back up the SQLite file first. Migrate **a copy** to head, then use `scripts/import_sqlite.py` to review a dry run against an empty migrated PostgreSQL destination; use `--apply` only for the intended cutover. Do not migrate or overwrite the original merely to test a release. Sessions, recovery links and queued emails are intentionally not imported. Existing imported accounts will need sign-in and, in production, email verification. The runbook explains backup/restore and restricted-role setup. Run a restore exercise before launch.

## 4. Deploy a preview and enable jobs

Deploy the configured preview via the Vercel dashboard/Git integration. Provider setup and the actual Vercel build/runtime are still to be verified in the cloud. `/api/health` should return `{"status":"ok"}`. `/api/ready` remains 503 until a successful retention job records freshness; this is expected before schedules are enabled.

Create these two schedules in QStash. The destination is the exact `${PUBLIC_WEB_URL}/api/jobs/run`, method POST and JSON content type:

| Schedule ID | UTC cron | Body |
| --- | --- | --- |
| `petadvice-SITEKEY-mail` | `*/15 * * * *` | `{"kind":"mail"}` |
| `petadvice-SITEKEY-maintenance` | `0 * * * *` | `{"kind":"maintenance"}` |

The helper derives `SITEKEY` from the site origin so preview and production schedules cannot overwrite each other in a shared QStash account. Its plan prints the exact IDs to use in the console. Keep that origin stable.

Set six retries with `min(600000, 60000 * pow(2, retried))` delay (milliseconds). This coordinates with the outbox's retry timing. [QStash schedules](https://upstash.com/docs/qstash/features/schedules) support stable schedule IDs, so updating avoids duplicate schedules. The included helper defaults to showing a plan:

```sh
.venv/bin/python scripts/configure_jobs.py
# Only after configuring the intended environment and reachable callback:
.venv/bin/python scripts/configure_jobs.py --apply
```

The helper creates/updates remote schedules and requests an initial maintenance callback for readiness when explicitly invoked with `--apply`. Run it from a private environment containing the intended deployment variables; Python loads a root `.env` if present, but does not automatically load `.env.local`. For protected previews, configure `VERCEL_AUTOMATION_BYPASS_SECRET` before applying schedules. Both immediate triggers and the schedule helper forward the header and request header redaction in QStash. Vercel bypass credentials apply to all deployments in a project; use separate Vercel projects when that isolation is required; verify this in the cloud.

Each committed verification/recovery email triggers a callback with only `{"kind":"mail"}`. A failed wakeup leaves the encrypted PostgreSQL outbox intact for the 15-minute reconciliation schedule. Mail callbacks send at most three messages; expired/superseded links are discarded. Provider failures or additional pending work return 503 so QStash retries. Resend receives a stable per-message [idempotency key](https://resend.com/docs/api-reference/emails/send-email), valid at the provider for 24 hours. Delivery remains at least once; SMTP has no comparable deduplication guarantee. The mail payload, recipient and link tokens never pass through QStash.

Callbacks require [QStash signature verification](https://upstash.com/docs/qstash/howto/signature) of the current/next key, issuer, exact destination, expiry, not-before time and raw body hash. Arbitrary public POSTs cannot run jobs. Repeated valid callbacks are safe. Cleanup processes at most 200 records per category, retrying full batches before recording freshness. Guest access expires immediately even if cleanup is delayed. An hourly retention schedule normally removes expired records within the next run, longer during outages/backlogs. Readiness permits a 90-minute maintenance heartbeat in scheduled mode and reports mail delayed beyond ten minutes. Avoid a frequent `/ready` polling monitor if database scale-to-zero matters; `/health` is a lighter liveness check.

## 5. Verify and promote

On the isolated HTTPS preview, verify the landing page and public dog/cat Learn/Care, guest check completion, explanation/answer recap, download and browser Print → Save as PDF. Confirm expired guest access and deletion, signed-in pet switching/history, old saved reports, and that checks never appear in browser API caches.

Verify real email delivery to test recipients, verification, superseded links, recovery, password reset revocation and logout. Confirm HttpOnly/Secure/SameSite cookies, origin rejection, private `no-store` responses and separate Redis rate limits. Test a signed job through QStash, invalid signature rejection, duplicate delivery, a failed/retried email, pending work, and retention/readiness. Verify CDN asset headers, service-worker updates, `/api` routing and mobile print layout. These cloud checks cannot be replaced by local mocked provider tests.

Before promotion, back up the production database, apply migrations once in a controlled release step, configure/verify production schedules and secrets, then promote the tested release and rerun a synthetic guest smoke check. Do not rely on function startup or the frontend build to apply migrations. Stop preview schedules when no longer needed, and do not leave callbacks pointing at old deployment URLs. For rollback, retain the new nullable column/index while rolling back app code; restoring an older database is a separate reviewed recovery operation.

## Operating the free setup

[Vercel Hobby](https://vercel.com/docs/plans/hobby) is intended for personal, non-commercial use. Keep this project within that scope or change plans when its purpose changes. The scheduled jobs create 120 baseline messages per day before immediate triggers/retries; [QStash's current free allowance](https://upstash.com/pricing/qstash) is 1,000/day. Database compute, Redis operations, email quotas, function usage and retry volume also need monitoring. Free operation depends on actual usage and provider terms; this preparation is not a guarantee of zero bills.

Configure quota alerts, job dead-letter alerts, email failures and periodic off-host encrypted backups. Choose/document backup and log retention and how deletions are reapplied after restores. No always-running Docker worker is needed on Vercel. The existing worker remains the default for local/container development.

## Local verification completed

On 2026-10-10, all 92 backend tests passed, including isolated PostgreSQL/Redis integration tests and HTTP guest/account smoke checks through the release entrypoint at `/api`. All 11 frontend tests, frontend lint, TypeScript/Vite compilation and the Vercel asset build passed. Alembic upgraded a disposable SQLite database to `0004` and reported no pending model changes.

Browser checks covered public dog/cat content and search, urgency explanations and recorded answers, downloaded HTML, the two-page print/PDF view, private saved-check reopening, pet switching and mobile layout. Screenshots are in [the release evidence directory](audit/release-2026-10-10/). Provider calls were tested locally with controlled substitutes; an actual Vercel deployment, real email delivery and QStash callbacks still require the cloud checks above.

The temporary browser preview, API, PostgreSQL and Redis services were stopped after testing. The original local SQLite database was not migrated or modified for these checks. Apply `alembic upgrade head` with the intended local configuration before starting that database with this release, or follow the copy/import procedure above for cloud cutover.
