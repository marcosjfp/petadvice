# PETAdvice tester beta hosting

Updated 2026-10-23. The owner requested external testers on the existing main address.

Main address: https://petadvice.vercel.app

Production beta deployment: `dpl_HdSwyqvgVjSsGvzRsb5QZ2eGfJoK`, built from the local
`2fa3a5e` checkout plus the reviewed working changes. This is an explicitly enabled test
beta with email verification/recovery disabled, a visible fictional-data notice and
`noindex,nofollow` metadata. It is not a completed full product launch.

Vercel Standard Protection keeps deployment URLs and previews gated; the main production
domain is available without a Vercel account. The earlier private preview remains at
https://petadvice-private-preview-marcosjfp.vercel.app and uses its original Preview flags.
Do not promote that old Preview build; the main beta has its own Production configuration.

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
| Maintenance schedule | `petadvice-d4e26350878f-maintenance`, `0 * * * *` UTC |

No payment method or paid service upgrade was added. Provider free allowances still apply.
The connected Vercel plugin rejected team-scoped writes, so the owner authorized the Vercel
CLI. Upstash's plugin initially supplied skills but no management tools; its signed-in
console was used to create Redis and read this application's service credentials. The
separate Vercel Marketplace Upstash installation still reports unaccepted terms; it is not
needed for these directly provisioned resources. Do not provision duplicates when resuming.

## Account behavior

`ACCOUNTS_WITHOUT_EMAIL_BETA=true` enables signup/login with Argon2id password hashes,
revocable sessions, Secure/HttpOnly/SameSite cookies, pet profiles and saved check history.
Guest checks, Learn, Care, reports and data controls remain available.

Email verification and recovery endpoints are explicitly disabled. No email outbox entries
or recovery/verification tokens are created at signup. The UI explains that forgotten
passwords cannot be reset through the app. Only synthetic test information should be used.

This beta exception requires `VERCEL_ENV=production` and `APP_ENV=production`. Both Preview flags are false in Production. The existing Preview-only exceptions still refuse the Production target. Normal production configuration continues to require real email delivery, operator/contact details and a published privacy policy. The frontend derives its test flags from the server configuration.

## Credentials and database

The ignored `.vercel/.env.preview.local` and `.vercel/.env.beta.local` are the private local configurations (mode 0600,
inside a mode-0700 `.vercel` directory). The local project link is `.vercel/project.json`.
The original development `.env.local` was preserved; Vercel linking added its local OIDC token.

Application credentials are saved in separately scoped Vercel Preview and Production variables. Non-sensitive URLs are Config values; database, Redis, signing and automation credentials are Secrets. The beta has an independent JWT secret; its test database, Redis and QStash resources are shared with the private preview to stay within the existing free setup. Isolate real Production data before leaving the test beta.
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

The browser then exposed a separate packaging failure: the API worked while the homepage
returned `Frontend has not been built`. Vercel's Python builder omits `public/` from the
function bundle by default. `functions.server.py.includeFiles = "public/**"` now explicitly
includes the generated frontend for runtime asset serving and SPA navigation fallback.
The upload ignore rule is anchored to `/public` so it excludes the generated root copy
while retaining `web/public` source images for the build.
The live smoke check also requires HTML plus working JavaScript, CSS, icon and manifest
responses, so backend health alone cannot pass deployment verification.

Vercel assigned the project's first upload to Production despite the Preview flag. It stayed
behind Vercel authentication and had no application database credentials. That initial
upload was removed; subsequent builds were verified as Preview through Vercel's API.

Only the main-domain hourly maintenance schedule is enabled. The old private-preview schedule `petadvice-cde77a61de9d-maintenance` was paused after the main callback succeeded; both test deployments share the maintenance heartbeat. No mail schedule is installed. Signed
QStash callbacks use a private automation header to pass Vercel authentication and still
must pass the application's signature/body/destination/expiry checks. Schedule API output
was checked to ensure the bypass header is redacted. QStash accepts the specific form
`header[x-vercel-protection-bypass]` for `Upstash-Redact-Fields`; the old `headers` form
was rejected by this region. See [Upstash's redaction documentation](https://upstash.com/docs/qstash/howto/redact-fields).

## Verification

- 93 backend tests passed; 6 infrastructure tests skipped in the local suite.
- All 14 frontend tests, frontend lint, standard build and the guest-only build passed.
- Migration tests passed; real restricted session/transaction pooler and Redis connections passed.
- Live guest flow: questions, result, access-token isolation, export and deletion passed.
- Live homepage, JavaScript, CSS, logo, manifest and SPA navigation fallback passed.
- Live account flow: signup, secure cookie, pet profile, saved check/history, logout,
  password login, reauthentication and account deletion passed.
- Live verification and recovery endpoints rejected requests as intended.
- Unsigned maintenance was rejected; QStash's real signed initial callback succeeded.
- `/api/ready` returned `200` with `{"status":"ready"}`.
- The scheduled bypass header was redacted. Staging tests passed behind Vercel protection before the main address was opened. A complete main-domain run then passed without any Vercel bypass credentials. Anonymous preview/deployment requests still redirected to Vercel login.
- Synthetic account/pet/check/session tables were empty after test cleanup; email/action
  tables were empty, and the maintenance heartbeat was present.
- Browser verification rendered the main-domain homepage, logo and Tester beta notice. The final homepage was left open for the owner. Main-domain signed maintenance delivery returned HTTP 200.
- The newly available Upstash connector confirmed the existing EU plan is Free and the
  single active maintenance schedule's latest callback succeeded.

The ignored `.vercel/smoke_preview.py` verifies the private Preview only. `.vercel/smoke_beta.py` is separately restricted to the authorized main beta and temporary staging alias; it creates and deletes only its own synthetic data. Its public-main run sends no Vercel bypass credentials.

The temporary beta staging alias is removed after verification. Root GET and HEAD requests also serve the homepage when no explicit HTML Accept header is supplied.

## Before a full product launch

Configure real email delivery and recovery/verification, disable preview/beta exceptions,
complete operator/privacy policy details and backup/log retention, isolate Production
resources and secrets, and follow the remaining cloud checks in
[the release guide](../vercel-release.md). Keep deployment preview protection enabled. The owner has explicitly requested tester access on the main domain; full-release preparation remains outstanding.

Mobile layout correction published 2026-10-24; see [phone verification](../verification/mobile-2026-10-24/README.md) for screen captures, responsive sizes and native iPhone testing limits.
