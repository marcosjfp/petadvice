# PETAdvice — Phase 1 & Phase 2 Build Guide

> Companion to `petadvice-app-spec.md` (vision, legal guardrails, data schema, content architecture) and `petadvice-content-batch-phase0.json` (seed content). Hand all three to a coding agent together — this file is the *ordered build checklist*; the spec is the source of truth for schema, API shape, and legal boundaries. Keep all three in `docs/` (or similar) in the repo so an agent can find them without being told twice.

---

## Hard constraints — condensed from spec §2 (don't skip this)

An agent building features from this checklist alone, without re-reading the full spec, should still respect these:

- Never output a specific diagnosis for a specific animal — urgency band + general guidance only.
- `home_care_guidance` is populated **only** when `urgency_default`/`resulting_urgency` is `monitor_home`. Anything else gets referral guidance, no home-treatment steps.
- Urgency only escalates during a triage session, never de-escalates.
- Every `red_flags` entry needs vet sign-off before it ships — this is not optional polish, it's the actual safety mechanism.
- GDPR: consent, export, and deletion for owner account data, planned from the start, not retrofitted.
- Health/medical-domain data must never be used for advertising or data-mining purposes (this is an explicit Apple *and* Google Play requirement too — see §2.5 below — so it's a hard constraint on monetization design, not just a nice-to-have).

---

## PHASE 1 — MVP (FastAPI backend + PWA)

### 1.1 Prerequisites

- Python 3.12+, Node 20+, git repo initialized, the two companion docs committed under `docs/`
- Pick (free-tier is fine for now) hosting accounts before you need them: backend host (Render or Fly.io), frontend host (Vercel or Netlify) — prefer **EU region** given GDPR and your Ireland/EU user base

### 1.2 Backend — build in this order

1. Scaffold the FastAPI project matching the structure in spec §10.
2. Add **SQLModel** (pairs naturally with the Pydantic models already in spec §4 — same author, less duplication than plain SQLAlchemy).
3. Copy the Pydantic models from spec §4 into `app/models/schema.py` verbatim, including the `Sex`/`NeuterStatus` enums. Convert only `Pet` (and later `Owner`, `TriageSession`) into SQLModel *table* models — they're the genuinely relational/dynamic entities. Keep `ConditionEntry` and `PreventiveCareItem` as plain Pydantic, loaded from JSON, not DB tables (this matches the JSON-file, PR-reviewable content workflow in spec §8).
4. Build a content loader service that reads `petadvice-content-batch-phase0.json` at startup and validates every entry against the `ConditionEntry`/`PreventiveCareItem` models. **Fail startup loudly if anything doesn't validate** — this is your schema-drift tripwire as the content library grows.
5. Implement `services/life_stage_calculator.py` using the life-stage tables in spec §3.2 (breed-size-dependent thresholds for dogs, DOB-based bands for cats).
6. Implement `services/triage_engine.py` per the flow in spec §6: symptom_tag lookup → ordered questions → `escalate_if` checks → `red_flags` checks against the pet's `environment_factors`/`applicable_sex`/`applicable_neuter_status` → take the *highest* urgency triggered.
7. Implement the API routes from spec §7 one at a time, each with its own test before moving to the next.
8. Set up SQLite for local dev, Alembic for migrations (swap to Postgres later without changing the model layer).
9. Write a `pytest` suite — prioritize `triage_engine` (this is the highest-stakes code in the app) and `life_stage_calculator` breed-size boundary cases over UI polish.
10. Sanity-check the auto-generated OpenAPI docs against spec §7 — cheap free QA.

### 1.3 Frontend (PWA) — build in this order

1. Scaffold Vite + React + TypeScript + Tailwind.
2. Add `vite-plugin-pwa` for manifest + service worker — this is what makes it installable, and it's also the thing Phase 2's Capacitor wrapper will build on top of, so get it right now rather than retrofitting.
3. Pet profile screens: create/edit pet — species, breed, breed size, DOB, weight, `environment_factors`, `sex`, `neutered`.
4. Triage flow: symptom picker → dynamic question steps → result screen. Make the urgency bands *visually* distinct — `emergency_now` should look and feel urgent, `monitor_home` should look calm. This isn't just design polish, it's part of the guidance actually landing.
5. Condition library: browsable/filterable by species, category, life stage; detail view per entry.
6. Preventive care calendar: grouped by "upcoming," driven off each pet's computed `life_stage`.
7. A persistent, always-easy-to-find emergency red-flag reference (per spec §5 MVP scope) — not buried three taps deep.
8. Responsive pass across mobile/tablet/desktop.

### 1.4 Content pipeline

- `petadvice-content-batch-phase0.json` lives in `app/content/` as seed data.
- Before it reaches a real user: run the §8 review workflow — your wife's first pass, then a registered vet's sign-off specifically on the `emergency_now`/`vet_24h` entries — and only then set `vet_reviewed_by` + `last_reviewed_date`.
- One entry (prostatic disease) currently has a placeholder source — don't let that one ship un-sourced.

### 1.5 Deployment

- Backend: Render or Fly.io, EU region.
- Frontend: Vercel or Netlify (or same host behind a reverse proxy).
- No secrets committed — DB URL, CORS origins, etc. via environment variables.
- Basic uptime/error monitoring (even a free tier — UptimeRobot, Sentry free tier) before calling this "done."

### 1.6 Phase 1 — Definition of Done

- [ ] All MVP features from spec §5 implemented
- [ ] Full seed content batch loads and passes schema validation on startup
- [ ] At minimum, all `emergency_now` content vet-reviewed and signed off
- [ ] `triage_engine` test suite green, including every red-flag escalation case
- [ ] Deployed over HTTPS, installable as a PWA
- [ ] Privacy policy page live (cheap to do now — Phase 2's Play Store requirement below needs it anyway)

---

## PHASE 2 — Native app, accounts, notifications, multi-pet

### 2.1 Native wrapper approach

- **Capacitor.js**, wrapping the already-validated Phase 1 PWA build — this reuses all Phase 1 frontend work instead of a rewrite, and matches the roadmap's "wrap the validated MVP" framing directly.
- iOS needs an Apple Developer Program membership ($99/yr); Android needs a Google Play Developer account ($25 one-time). Get both started early — review/verification can take days.
- A React Native rewrite is a fallback if you later want a more fully-native feel, but it's not needed to hit Phase 2's goals.

### 2.2 Accounts / auth

- Decision point: self-rolled FastAPI auth (`fastapi-users` + JWT) vs. a managed provider (Firebase Auth). Since push notifications (2.3) already pull in Firebase, using Firebase Auth too avoids standing up a second identity system — reasonable coupling for where the app is at; revisit if you outgrow it.
- Build GDPR touchpoints now, not later: explicit consent at signup, an account data export endpoint, an account deletion endpoint that cascades to pets/triage sessions, and a documented retention period.

### 2.3 Push notifications

- Firebase Cloud Messaging (FCM) on the backend, the Capacitor Push Notifications plugin on the client (covers both iOS-via-APNs and Android through one integration).
- Trigger source: `PreventiveCareItem.recurrence` / `trigger_age_days`, computed server-side into a per-pet reminder schedule.
- Build notification opt-out/preferences from day one — expected by users, and by both stores' review process.

### 2.4 Multi-pet household support

- The good news: `Pet` already keys off `owner_id` (spec §4), so the backend barely changes here.
- Mostly frontend work: a pet-switcher on the dashboard, an "add another pet" flow, and confirming triage sessions and preventive-care reminders stay correctly scoped per `pet_id` (already true if 1.2/§7 were implemented as specified).

### 2.5 App store submission — current requirements (checked September 2026)

**Apple:**
- Apps seen as offering diagnosis/treatment, or that risk generating inaccurate health data, get more vigorous review. Lean explicitly on the "urgency + general guidance, not diagnosis" framing from spec §2 in both the app's copy and your App Review notes.
- Health-domain data must not be used for advertising or other data-mining purposes — a hard constraint on monetization, not just a submission checkbox.
- Include an in-app reminder to consult a vet before acting on guidance (matches what's already in spec §2's copy rule of thumb).

**Google Play:**
- Complete the **Health apps declaration** in Play Console (Policy → App content) before submitting — required for any app with health/medical-related features.
- A privacy policy must be live at a public, non-geofenced URL (not a PDF), linked both in Play Console and inside the app itself.
- Policy prohibits misleading or harmful health functionality — your §8 vet-review gate is the actual substance behind this, not just paperwork to satisfy reviewers.

*(These policies get revised periodically on both platforms — worth a quick re-check against the current published guidelines right before you actually submit, not just at build time.)*

### 2.6 Phase 2 — Definition of Done

- [ ] Installable native builds on TestFlight (iOS) and the Play internal testing track (Android)
- [ ] Accounts working end-to-end, including GDPR export/delete
- [ ] Push notifications delivering preventive care reminders on schedule
- [ ] Multi-pet flow tested with 2+ pets on one account
- [ ] Google Play Health apps declaration completed; Apple submission notes reference the spec §2 guardrails
- [ ] Privacy policy live and linked from both stores and in-app

---

## Before Phase 3

Revisit spec §12's open decisions — in particular, ask-a-vet staffing now has real weight to it, since accounts and auth already exist to support it once you're ready to add the liability surface that comes with it.
