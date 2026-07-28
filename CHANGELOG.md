# Changelog

All notable changes to DentalPin are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

The `v2.0` line is the first to ship with the post-Fase-B module
architecture: the monolithic `clinical` module is gone, replaced by
four purpose-built modules, and every official module now ships its
frontend as a Nuxt layer under its own Python package.

## [Unreleased]

## [2.1.0] - 2026-07-28

First release cut through the automated pipeline. The eleven modules that
landed since 2.0.0 — payments, copilot, verifactu, recalls, schedules,
notifications, periodontogram, clinical_notes, accounting_export,
migration_import, whatsapp_kapso — are listed per-PR in the generated
release notes and documented in their own module CHANGELOGs; the
narrative version of that work belongs to the next major.

### Added

- **Prebuilt images and a one-command install.** Tagging a release now
  builds and publishes `ghcr.io/martinezsalmeron/dentalpin-backend` and
  `-frontend`, and publishes the GitHub Release with notes taken from
  this file. `docker-compose.prod.yml` runs the stack straight from those
  images with no clone and no build; a Caddy container fronts both
  services on a single origin, so TLS is provisioned automatically from
  `PUBLIC_URL` and there is no CORS to configure. One image serves every
  deployment — Nuxt overrides `runtimeConfig.public.apiBaseUrl` from
  `NUXT_PUBLIC_API_BASE_URL` at boot rather than baking the URL in.

- **First-time setup assistant** (issue #85). A fresh install (no users)
  now bootstraps from the UI: `GET /api/v1/auth/setup/status` reports
  whether the system is initialized, and `POST /api/v1/auth/setup`
  atomically creates the first clinic + admin user + admin membership and
  returns tokens. The endpoint is self-closing (409 once any account
  exists). The frontend redirects unauthenticated visitors of an empty
  system to a 2-step `/setup` wizard (admin account → clinic basics);
  remaining configuration is handled by the existing onboarding checklist.

### Changed

- Removed the public `POST /api/v1/auth/register` endpoint. It created
  orphan users with no clinic membership (unusable, and unused by the UI);
  the first-run setup assistant replaces it.

- Alembic history squashed. The 29-migration main-linear chain
  inherited from Fase A collapsed into one `0001_core_initial` for
  core tables + 11 module-owned initials under
  `backend/app/modules/<name>/migrations/versions/<mod>_0001_initial.py`.
  Each module's initial lives in its own package so community module
  authors can pattern-match their own migrations on the official
  examples. Cross-module FKs live on the "late" side — the only
  circular dep (`appointment_treatments.planned_treatment_item_id`
  → `planned_treatment_items`) is created in `tp_0001` after both
  tables exist. Round-trip `upgrade head → downgrade base → upgrade
  head` is clean and `test_alembic_roundtrip` no longer xfails.

### Fixed

- `docker-compose.yml` hardcoded `http://localhost:8000` as the frontend's
  API base (build arg + runtime env), so the documented `API_BASE_URL` in
  `.env` had no effect and the app was unreachable from any device other
  than the Docker host — the browser resolved `localhost` to itself.
  Both now read `${API_BASE_URL:-http://localhost:8000}`.

- Clinic timezone selector only offered 15 curated European/American
  zones. It now lists the runtime's full IANA set (`Intl.supportedValuesOf`)
  in a searchable `USelectMenu`; the backend already validated against
  `zoneinfo`, so any IANA id was accepted all along.

## [2.0.0] - 2026-04-21

First release on the post-Fase-B module architecture. Covers the
full Fase B refactor (B.1 → B.6), the hardening pass (B.7), and the
Playwright E2E smoke suite (B.8). `main` is stable against the
12-module layout; the `clinical` module is gone.

### Added

- **Module `patients`** (`auto_install: True, removable: False`) —
  Patient identity, demographics, billing info. Endpoints under
  `/api/v1/patients/*`. Permissions under `patients.*`.
- **Module `patients_clinical`** (`auto_install: True, removable: True`)
  — normalized medical history with 7 tables
  (`patients_clinical_medical_context`, `_allergy`, `_medication`,
  `_systemic_disease`, `_surgical_history`, `_emergency_contact`,
  `_legal_guardian`). Endpoints under `/api/v1/patients_clinical/*`.
  Alerts (`/alerts`) now derive from real rows — actual SQL analytics
  over allergies / diseases is possible.
- **Module `agenda`** (`auto_install: True, removable: True`) —
  Appointment, AppointmentTreatment, Cabinet. Cabinets promoted from
  the `clinic.cabinets` JSONB to a real table with FK
  (`appointments.cabinet_id`). Endpoints under `/api/v1/agenda/*`.
- **Module `patient_timeline`** (`auto_install: True, removable: True`)
  — cross-module audit log, populated via event subscriptions.
  Endpoints under `/api/v1/patient_timeline/*`.
- Clinic metadata endpoints moved into core auth:
  `GET/PUT /api/v1/auth/clinics`.
- Nuxt layer support for every official module. Each module now ships
  `<module>/frontend/{pages,components,composables,i18n}` and is
  auto-discovered at boot via `modules.json`.
- New pytest marker `alembic_roundtrip` for the full
  `base → head → base → head` migration-chain check; excluded from
  the default pytest run, executed as a dedicated CI step.
- CI pipeline gains `manifest-consistency` and `frontend-typecheck`
  jobs (Nuxt `prepare` pass that catches broken Vue/TS imports across
  module layers).
- Playwright browser E2E suite under `frontend/tests/e2e/` — 16
  smoke tests covering admin navigation across every module layer,
  patient detail rendering, and per-role sidebar visibility. CI `e2e`
  job boots docker-compose + seeds demo + runs Playwright.
  `./scripts/e2e.sh` wrapper for local runs.

### Changed

- **Breaking — API paths**
  - `GET /api/v1/clinical/patients/*` → `GET /api/v1/patients/*`
  - `.../medical-history`, `.../alerts`, `.../emergency-contact`,
    `.../legal-guardian` → `/api/v1/patients_clinical/patients/{id}/...`
  - `GET /api/v1/clinical/appointments/*` → `/api/v1/agenda/appointments/*`
  - `GET /api/v1/clinical/clinics/*` → `/api/v1/auth/clinics/*`
  - Patient timeline read at `/api/v1/patient_timeline/patients/{id}`
- **Breaking — permissions**
  - `clinical.patients.*` → `patients.*`
  - `clinical.patients.medical.*` → `patients_clinical.medical.*`
  - `clinical.patients.emergency.*` → `patients_clinical.emergency.*`
  - `clinical.appointments.*` → `agenda.appointments.*`
  - `clinical.appointments.cabinets.*` → `agenda.cabinets.*`
- Every official module manifest's `depends` rewritten against the
  real modules (patients / agenda / catalog / budget) instead of the
  now-removed `clinical`.
- `Patient.active_alerts` property removed (alerts compute via
  `PatientsClinicalService.compute_alerts`).
- Dashboard + Settings sidebar entries are host-owned (see
  `frontend/app/utils/moduleRegistry.ts::HOST_NAV`); modules no
  longer publish `/` or `/settings`.
- Auth rate limiter only activates in `ENVIRONMENT=production`.
  Dev + test runs were tripping the 5/min `/login` cap during manual
  reloads and Playwright runs; production semantics unchanged.

### Removed

- **Breaking — module `clinical`** — fully deleted. All downstream
  depends point at the real owning modules.
- `patients.medical_history`, `patients.emergency_contact`,
  `patients.legal_guardian` JSONB columns dropped — data migrated to
  the normalized `patients_clinical_*` tables in
  `w3x4y5z6a7b8_add_patients_clinical_tables.py`.
- `clinic.cabinets` JSONB column dropped — replaced by the `cabinets`
  table in `v2w3x4y5z6a7_add_cabinets_table.py`.

### Frontend layer conventions

- Each layer's `nuxt.config.ts` must register
  `components: [{path: './components', pathPrefix: false}]`; the host
  overrides Nuxt's default auto-scan so this is load-bearing.
- Cross-layer type imports use `~~/app/types` (rootDir-relative, = host
  frontend) instead of `~/types` (srcDir-relative, which would scope
  to the current layer).

### Known gaps (deferred)

- Alembic chain still lives as a single main-linear list. The squash
  that breaks it into per-module branches (one clean initial per
  module) is deferred; `test_alembic_roundtrip` is `xfail` until
  then and exists purely to hold the infrastructure in place.
- Docs (`docs/diagrams/*`, `CLAUDE.md` examples) still reference the
  old `/api/v1/clinical/*` paths in a handful of illustrative spots;
  the primary `docs/technical/creating-modules.md` and `docs/technical/core-api.md` are
  up to date.
