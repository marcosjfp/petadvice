# PETAdvice protected account preview

Updated 2026-10-23. The owner authorized saving the service credentials and enabling
email/password accounts without email verification or password recovery for private testing.

Preview: https://petadvice-private-preview-marcosjfp.vercel.app

Vercel authentication protects all deployments. Sign in with the owning Vercel account
before using PETAdvice signup/login. This is a Preview deployment; no public Production
release is active. Do not promote the email-disabled build.

## Resources

| Resource | Configuration |
| --- | --- |
| Vercel project | `petadvice`, `prj_Yjf28HD3lYEtu5da9ttdVHAsvdeG` |
| Vercel team | `marcosjfpinheiro-gmailcoms-projects`, `team_3w7n7iRUfRwyZn5x9O0lmtFs` |
| Vercel runtime | FastAPI, repository root, Python 3.14, Node 24, function region `dub1` |
| Supabase project | `petadvice`, `jjtqrdrffruxuhqfjbkd`, organization `ibroxvzlsjawyozyssib` |
| Supabase region | Ireland, `eu-west-1`; quoted $0/month and approved by owner |
| Upstash Redis | `petadvice-preview-redis`, `a32cf4fa-5dbd-4bed-996b-6e21d615b1a6`, Ireland, Free, TLS |
| Upstash QStash | Existing EU instance `b9cd0d23-8a41-4dfb-958a-c308d2ee5bea`, Free |
| Maintenance schedule | `petadvice-cde77a61de9d-maintenance`, `0 * * * *` UTC |

No payment method or paid service upgrade was added. Provider free allowances still apply.
The connected Vercel plugin rejected team-scoped writes, so the owner authorized the Vercel
CLI. Upstash's plugin supplied skills but no management tools in this session; its signed-in
console was used to create Redis and read this application's service credentials. The
separate Vercel Marketplace Upstash installation still reports unaccepted terms; it is not
needed for these directly provisioned resources. Do not provision duplicates when resuming.

## Account behavior

`ACCOUNTS_WITHOUT_EMAIL_PREVIEW=true` enables signup/login with Argon2id password hashes,
revocable sessions, Secure/HttpOnly/SameSite cookies, pet profiles and saved check history.
Guest checks, Learn, Care, reports and data controls remain available.

Email verification and recovery endpoints are explicitly disabled. No email outbox entries
or recovery/verification tokens are created at signup. The UI explains that forgotten
passwords cannot be reset through the app. Only synthetic test information should be used.

This exception is restricted to `VERCEL_ENV=preview` with `APP_ENV=production`. The normal
Production validation still requires real email delivery, operator/contact details and a
published privacy policy. `GUEST_ONLY_PREVIEW=false` for this deployment; the earlier
optional guest-only mode remains available separately. The frontend build derives its
preview flags from the server flags to keep account controls consistent.

## Credentials and database

The ignored `.vercel/.env.preview.local` is the private local configuration (mode 0600,
inside a mode-0700 `.vercel` directory). The local project link is `.vercel/project.json`.
The original development `.env.local` was preserved; Vercel linking added its local OIDC token.

Application secrets were saved only to Vercel's Preview environment. Non-sensitive URLs
are Config values; database, Redis, signing and automation credentials are Secrets.
`DIRECT_DATABASE_URL` stays local for controlled migrations and was not deployed.
`.vercelignore` explicitly excludes `.vercel`, environment files, local databases and
private tooling directories. A deployment dry run verified these exclusions.

A temporary Redis credential copy was accidentally saved to TextEdit's iCloud folder.
It was moved to the protected local project folder and the accidental iCloud file was
removed. Intermediate Redis/QStash copy files were removed after the consolidated local
configuration was verified; their contents were not printed in chat.

Supabase uses the restricted `petadvice_app` login and private `petadvice` schema. The role
has no superuser, create-role, create-database, replication or bypass-RLS privileges.
Search path is `petadvice, public`. Runtime uses the transaction pooler on
`aws-0-eu-west-1.pooler.supabase.com:6543`; migrations use its session pooler on port 5432.
Both require TLS, database `postgres`, and pooled username
`petadvice_app.jjtqrdrffruxuhqfjbkd`.

Alembic migrations through `0005` were applied and `alembic check` reported no drift.
Migration `0005` aligns old UTC timestamp columns with the pinned SQLModel version's
aware datetime fields. A temporary historical UTC record was preserved by the migration
and then deleted. No original local data was imported or modified.

All nine private-schema tables have RLS enabled. Public API roles have no schema usage.
There are intentionally no row policies: the backend owns these private tables and enforces
application authorization; all other roles are denied. Supabase's advisor reports only
informational [RLS-without-policy findings](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
for that arrangement. App data is not exposed through the Supabase Data API, and accounts
continue to use the existing FastAPI authentication system rather than Supabase Auth.

## Build and maintenance

Vercel prefers `pyproject.toml` over `requirements.txt`. The project now declares the same
53 pinned dependencies as the existing requirements lock, with a checked `uv.lock`.
Update both dependency definitions together when upgrading packages. The first attempt
without project dependencies built successfully but failed to import FastAPI at runtime;
the corrected package definition fixed that failure.

Vercel assigned the project's first upload to Production despite the Preview flag. It stayed
behind Vercel authentication and had no application database credentials. That initial
upload was removed; subsequent builds were verified as Preview through Vercel's API.

Only the hourly maintenance schedule is enabled. No mail schedule is installed. Signed
QStash callbacks use a private automation header to pass Vercel authentication and still
must pass the application's signature/body/destination/expiry checks. Schedule API output
was checked to ensure the bypass header is redacted. QStash accepts the specific form
`header[x-vercel-protection-bypass]` for `Upstash-Redact-Fields`; the old `headers` form
was rejected by this region. See [Upstash's redaction documentation](https://upstash.com/docs/qstash/howto/redact-fields).

## Verification

- 91 backend tests passed; 6 infrastructure tests skipped in the local suite.
- All 13 frontend tests, frontend lint, standard build and the guest-only build passed.
- Migration tests passed; real restricted session/transaction pooler and Redis connections passed.
- Live guest flow: questions, result, access-token isolation, export and deletion passed.
- Live account flow: signup, secure cookie, pet profile, saved check/history, logout,
  password login, reauthentication and account deletion passed.
- Live verification and recovery endpoints rejected requests as intended.
- Unsigned maintenance was rejected; QStash's real signed initial callback succeeded.
- `/api/ready` returned `200` with `{"status":"ready"}`.
- The scheduled bypass header was redacted; anonymous access redirected to Vercel login.
- Synthetic account/pet/check/session tables were empty after test cleanup; email/action
  tables were empty, and the maintenance heartbeat was present.
- Browser access reached Vercel's login gate. An owning-account Vercel login is required
  to render the app interactively in that browser.

The ignored local `.vercel/smoke_preview.py` reruns the synthetic private Preview checks
and deletes its own data. Do not point it at a public or Production service.

## Before a public launch

Configure real email delivery and recovery/verification, disable preview exceptions,
complete operator/privacy policy details and backup/log retention, isolate Production
resources and secrets, and follow the remaining cloud checks in
[the release guide](../vercel-release.md). Keep visitor protection enabled until the owner
explicitly requests a public release.
