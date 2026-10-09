# PETAdvice

PETAdvice is a React/TypeScript frontend and FastAPI backend for general dog/cat symptom urgency and preventive-care information. It does not diagnose animals or replace veterinary care. The clinical content is awaiting veterinary review.

## Implemented functionality

- Guest symptom checks with branching questions and persistent emergency information.
- Account signup/login/logout, pet profiles and switching between pets.
- Species/life-stage filtering, structured urgency results and escalation.
- Searchable condition library with expandable guidance, red flags, sources and review status.
- Preventive-care titles, descriptions and recurrence information, including loading/empty/error states.
- Account data export and deletion with a confirmation step in the UI.
- PWA shell and manifest; checks require an online API. There are no notifications or scheduled reminders yet.

See [the code and application review](docs/modernization-review.md) for changes, evidence and prioritized remaining work.

## Local development

Use Python 3.13 and Node 24 (the versions tested locally). The frontend requires Node 22.12 or newer.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
npm ci --prefix web
npm run dev --prefix web -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite proxies `/api/*` to the backend and strips `/api`. Stay on the same frontend hostname when testing cookie sessions. API docs are at `http://127.0.0.1:8000/docs`.

Environment variables must be supplied by your shell or deployment provider; `.env.example` is documentation and is not automatically loaded by the backend. Vite reads `web/.env` for frontend settings.

## Authentication and deployment

Browser authentication uses a one-hour HttpOnly, SameSite=Lax session cookie. Production cookies are Secure. The browser no longer stores JWTs in localStorage. Existing localStorage sessions require signing in again. Existing bcrypt password hashes are upgraded to Argon2id after a successful login; existing passwords can still be used. New signup passwords require 15–128 characters. Email addresses are validated and normalized.

Bearer JWTs remain available for API clients. JWT verification requires expiration, issue time, subject, issuer and audience. Cookie-authenticated writes must send a trusted `Origin` header. CORS is not a replacement for this CSRF check.

Backend variables:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Default `development`; set `production` for Secure cookies and startup checks. |
| `JWT_SECRET_KEY` | Production requires a random value of at least 32 characters. Use the same stable secret across workers. Development without a configured secret generates a process-local secret, so restarting signs users out. |
| `CORS_ORIGINS` | Exact trusted frontend origins, comma-separated. Never use `*` with credentialed requests. |
| `DATABASE_URL` | Defaults to `sqlite:///./petadvice.db`. SQLite is for local development/demos. |

Frontend `VITE_API_BASE_URL` defaults to `/api`. Deploy the frontend and API on the same origin through a reverse proxy that strips `/api`, or use HTTPS subdomains of the same site with explicit CORS configuration. Separate unrelated Vercel/Render domains do not work with SameSite=Lax cookies. The development proxy does not exist in a static production build or `vite preview`; configure the production proxy explicitly.

The supplied `render.yaml` sets production mode and generates a signing secret. It is still a demo backend: persistent storage, a production domain/proxy, migrations and operational protections need separate setup. Do not treat its ephemeral SQLite storage as suitable for real accounts.

Private API responses use `Cache-Control: no-store`. The service worker has no runtime API cache and excludes `/api` from navigation fallback. Updates do not automatically reload an active assessment. Install/offline behavior still needs testing on actual mobile devices; original brand images remain large.

## Triage safeguards

- Unsupported symptoms are rejected before creating a guest pet/session.
- Only the current question and one of its configured answers are accepted.
- Completed sessions cannot be rewritten.
- Results cannot be retrieved until the question flow is complete.
- Applicable content is never replaced with other-species or known incompatible guidance.
- The highest applicable default urgency wins. No applicable content produces referral guidance, not home-care reassurance.
- Content loading validates unique IDs/options, answer mappings, branch references, symptom boundaries, entry points and absence of cycles.

These are software safeguards. Guest profiles do not capture age/sex/neuter status, some decision trees are sparse, and medical appropriateness requires veterinary review. No release approval is implied.

## Verification

```sh
.venv/bin/python -m pytest -q
npm run lint --prefix web
npm test --prefix web
npm run build --prefix web
npm audit --prefix web
```

Backend API tests use an isolated in-memory database and do not run migrations against the developer's database. Frontend tests cover pet switching, correct preventive-care rendering, result retry without a second answer submission, and condition search/detail behavior. GitHub Actions runs tests, lint, build and the frontend vulnerability audit; workflow actions are pinned to verified release commits.

`requirements.in` holds compatible direct dependency ranges. `requirements.txt` locks transitive versions and integrity hashes. To intentionally refresh it:

```sh
uv pip compile --generate-hashes requirements.in -o requirements.txt
```

The npm lockfile records tested compatible upgrades. Major TypeScript/PWA upgrades should be reviewed and verified separately.

## Before public release

Prioritize veterinary review and representative clinical scenarios; durable PostgreSQL storage with migrations/backups; rate limiting and anti-abuse controls; session revocation and password recovery; an operator-specific privacy policy and retention policy; guest-data cleanup; and production observability. Data export/deletion features alone do not establish GDPR compliance.

`petadvice.db` was already tracked by Git. The new ignore rules prevent new databases being added but do not remove an already tracked file or its history. Preserve a local backup and decide how to remove it from version control before sharing the repository. Do not commit real secrets or personal data.
