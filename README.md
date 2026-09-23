# PETAdvice

PETAdvice is a responsive web app and installable PWA that helps dog and cat owners make a calmer, better-informed next decision when something seems wrong.

It provides:

- Plain-language information about common symptoms and concerns.
- Structured triage questions that return an urgency level.
- General guidance for monitoring at home or contacting a veterinary practice.
- Preventive-care information based on species and life stage.
- A persistent emergency reference for signs that should bypass the normal flow.
- Profiles for multiple pets, with switching available throughout the app.

PETAdvice is a first point of reference. It is **not a diagnostic tool, does not diagnose a specific animal, and does not replace a veterinary examination**.

## Current Status

Phase 1 MVP is implemented:

- FastAPI backend.
- SQLModel persistence with SQLite for local development.
- Versioned JSON content batches loaded and validated at startup.
- Structured triage engine with monotonic urgency escalation.
- Life-stage calculation for dogs and cats.
- React + TypeScript + Vite frontend.
- PWA manifest and service worker generation.
- Pet creation and switching.
- Condition library and preventive-care views.
- Local and production build validation.

Phase 2 is not implemented yet. It will cover authentication, GDPR export/deletion, notifications, multi-pet account workflows, and Capacitor native builds.

## Safety Boundaries

The application follows these rules:

- Outputs describe urgency and general next steps, never a diagnosis.
- Urgency can escalate during a triage session but never de-escalate.
- `home_care_guidance` is allowed only for entries whose default urgency is `monitor_home`.
- Entries above `monitor_home` return referral guidance rather than home-treatment instructions.
- Triage answers must match the configured options for the question.
- Species and known life stage are used to filter condition candidates.
- Emergency signs remain visible outside the normal triage flow.
- Content must be reviewed before release, especially red flags and emergency entries.

Clinical content still requires veterinary review before being presented as approved content. The JSON fields `vet_reviewed_by` and `last_reviewed_date` are intentionally empty until that review has happened.

## Technology

### Backend

- Python 3.12+
- FastAPI
- SQLModel
- Pydantic 2
- SQLite locally
- Uvicorn
- Pytest

### Frontend

- React
- TypeScript
- Vite
- `vite-plugin-pwa`
- CSS with responsive layouts and the PETAdvice brand assets

## Project Structure

```text
.
├── app/
│   ├── api/
│   │   ├── conditions.py
│   │   ├── pets.py
│   │   ├── preventive_care.py
│   │   └── triage.py
│   ├── content/
│   │   ├── loader.py
│   │   ├── petadvice-content-batch-homecare.json
│   │   ├── petadvice-content-batch-phase0.json
│   │   └── triage_questions.json
│   ├── models/
│   │   └── schema.py
│   ├── services/
│   │   ├── life_stage_calculator.py
│   │   └── triage_engine.py
│   ├── db.py
│   └── main.py
├── tests/
│   └── test_backend.py
├── web/
│   ├── src/
│   │   ├── assets/brand/
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── api.ts
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── petadvice-app-spec.md
├── petadvice-build-guide-phase1-2.md
├── petadvice-content-batch-homecare.json
├── petadvice-content-batch-phase0.json
├── petadvice-phase1-full-code.md
├── render.yaml
└── requirements.txt
```

## Prerequisites

Install:

- Python 3.12 or newer.
- Node.js 20 or newer.
- npm.
- Git.

Python 3.14 and Node 24 are known to work locally with the current project.

## Run Locally

### 1. Install backend dependencies

From the project root:

```bash
python3 -m pip install -r requirements.txt
```

### 2. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at:

- Health check: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

### 3. Install frontend dependencies

In another terminal:

```bash
npm install --prefix web
```

### 4. Start the frontend

```bash
npm run dev --prefix web -- --host 127.0.0.1
```

Open the URL printed by Vite, normally:

```text
http://127.0.0.1:5173/
```

If that port is busy, Vite chooses another port. The backend accepts the standard local ports `5173` and `5174` by default.

## Environment Variables

The frontend uses:

```text
VITE_API_BASE_URL
```

If it is not set, the frontend calls `http://localhost:8000`.

Example for a deployed frontend:

```bash
VITE_API_BASE_URL=https://your-api.onrender.com
```

The backend uses:

```text
DATABASE_URL
CORS_ORIGINS
```

`DATABASE_URL` defaults to local SQLite:

```text
sqlite:///./petadvice.db
```

`CORS_ORIGINS` is a comma-separated list of allowed frontend origins. See [.env.example](.env.example).

Example:

```text
CORS_ORIGINS=https://your-app.vercel.app
```

Do not commit real secrets or private service credentials.

## Tests and Builds

Run the backend tests:

```bash
pytest -q
```

Run the frontend production build:

```bash
npm run build --prefix web
```

Run both checks together:

```bash
pytest -q && npm run build --prefix web
```

The current suite covers:

- Content batch validation.
- Multi-file content loading.
- Duplicate condition protection.
- Dog and cat life-stage boundaries.
- Emergency urinary triage.
- Monotonic urgency escalation.
- Invalid triage answer rejection.
- Home-care red-flag escalation.
- Species filtering, including exclusion of cat hairball guidance for dogs.

## Content Workflow

Content lives in versioned JSON files under `app/content/`.

The loader automatically discovers files matching:

```text
*content-batch*.json
```

This means a new content batch can be added without changing loader code.

When adding a batch:

1. Follow the Pydantic schema in `app/models/schema.py`.
2. Give every condition a unique `id`.
3. Add a real source citation.
4. Set `urgency_default` carefully.
5. Use `home_care_guidance` only for `monitor_home` entries.
6. Add red flags for changes that should escalate urgency.
7. Add triage questions for symptoms where answers materially change urgency.
8. Run `pytest -q`.
9. Have the content reviewed by the veterinary reviewer.
10. Add final sign-off metadata only after review.

The current content includes the Phase 0 reproductive/urinary batch and a home-care batch covering gastrointestinal, respiratory, dermatological, parasite, and musculoskeletal concerns.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/pets` | Create a pet profile |
| `GET` | `/pets/{pet_id}` | Retrieve a pet and computed life stage |
| `GET` | `/pets?owner_id=...` | List an owner's pets |
| `GET` | `/conditions` | Browse and filter condition entries |
| `GET` | `/conditions/{condition_id}` | Retrieve one condition entry |
| `GET` | `/triage/questions?symptom_tag=...` | Load questions for a symptom |
| `POST` | `/triage/start` | Start a triage session |
| `POST` | `/triage/{session_id}/answer` | Submit a validated answer |
| `GET` | `/triage/{session_id}/result` | Compute the final urgency and guidance |
| `GET` | `/preventive-care` | Browse preventive-care items |

## Free Deployment

The recommended free MVP setup is:

- GitHub for source control.
- Render for the FastAPI backend.
- Vercel for the Vite frontend.

### Backend on Render

Use the included [render.yaml](render.yaml), or configure manually:

```text
Build command: pip install -r requirements.txt
Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health check path: /health
```

Set:

```text
CORS_ORIGINS=https://your-frontend.vercel.app
```

After deployment, verify:

```text
https://your-api.onrender.com/health
https://your-api.onrender.com/docs
```

### Frontend on Vercel

Set the project root directory to `web` and use:

```text
Build command: npm run build
Output directory: dist
```

Set:

```text
VITE_API_BASE_URL=https://your-api.onrender.com
```

Then open the deployed Vercel URL and test profile creation, pet switching, triage, Learn, and Care Plan.

### Free-hosting limitation

The current local database is SQLite. Free web instances can lose local files when they restart or redeploy. This deployment is appropriate for demos and early MVP validation, not real user data.

Before accepting real accounts or personal data, move to managed PostgreSQL, add migrations, implement authentication, and complete GDPR export/deletion workflows.

## Branding

The supplied logo assets are bundled in `web/src/assets/brand/`:

- `Logo_new.png`: main introductory screen.
- `Logo_Just_Name.png`: compact application header.
- `Logo_Just_Pets.png`: compact pet selector.

## Roadmap

### Phase 1

- Validate the content library with veterinary review.
- Improve symptom coverage and triage decision trees.
- Add proper condition detail screens and richer preventive-care scheduling.
- Move persistence to managed PostgreSQL before real users.
- Add privacy policy and production monitoring.

### Phase 2

- User accounts and authentication.
- GDPR consent, export, retention, and deletion.
- Push notifications.
- Multi-pet account workflows.
- Capacitor iOS and Android builds.

### Phase 3

- Licensed ask-a-vet service.
- Photo input only after legal and clinical review.
- Additional languages and markets with country-specific regulatory checks.

## License and Medical Disclaimer

This repository is an early product prototype. Content requires appropriate veterinary review before release.

PETAdvice provides general educational and urgency guidance. It does not diagnose conditions, prescribe treatment, or replace a veterinary examination. In an emergency, contact an emergency veterinary service immediately.
