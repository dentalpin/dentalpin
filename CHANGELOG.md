# Changelog

All notable changes to DentalPin are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

The `v2.0` line is the first to ship with the post-Fase-B module
architecture: the monolithic `clinical` module is gone, replaced by
four purpose-built modules, and every official module now ships its
frontend as a Nuxt layer under its own Python package.

## [Unreleased]

- **Arabic (`ar`) interface with full RTL support** — core app at exact
  key parity, MSA register with Latin clinical/financial glosses, and
  right-to-left layout wiring: the `ar` locale ships `dir: 'rtl'` in
  `nuxt.config.ts`, the app shell drives `html[dir]` from the active
  Nuxt UI locale (`app.vue`), and the Cairo Variable font joins the
  system font stack as the Arabic glyph carrier. FDI tooth-chart
  components in `odontogram`/`periodontogram` pin `dir="ltr"` so anatomy
  stays left-right. `i18n.config.ts` gains a CLDR-exact `ar`
  `pluralRules` entry (zero/one/two/few/many/other) alongside the
  existing `pl` one.

## [2.5.0] - 2026-09-02

### Added

- **Nine new optional modules** (all manual-install from the admin UI):
  - **`inventory`** — stock list with low-stock alerts (#277), then
    the core upgrade: unit cost tracking, stock movements with an
    audit trail and automatic deduction on completed treatments (#289,
    thanks @lamanji).
  - **`treatment_consumables`** — links catalog treatments to the
    inventory items they consume; feeds the auto-deduction above
    (#280, thanks @lamanji).
  - **`suppliers`** — supplier and procurement base module on top of
    `contacts`; backend-only foundation for the purchasing suite
    (#359, thanks @lamanji).
  - **`medication_catalog`** — clinic-wide medication list (#279,
    thanks @lamanji).
  - **`staff_tasks`** — staff handoff board (#267, thanks @lamanji).
  - **`activity_journal`** — append-only staff activity log with
    resolved actor names (#278, thanks @lamanji).
  - **`documents`** — branded PDF generation module
    (#319, thanks @lamanji).
  - **`whatsapp_webhook`** — WhatsApp via a signed webhook, the
    zero-onboarding adapter for any PBX/automation tool; HMAC signing
    and URL safety moved into `app/core/webhooks` so other adapters
    can share them (#347, #63, thanks @ZoliQua).
  - **`telephony`** — CTI gateway phase 1: HMAC-verified inbound call
    events, E.164 normalization, caller→patient matching, persistent
    call log and a screen-pop toast for ringing calls; the pop poll
    backs off to a 10-minute status probe on unconfigured clinics
    (#349, #366, #64, thanks @ZoliQua).
- **Integrations Phase 2** (#65): eight webhook triggers with a stable
  `event_id`, a token-authenticated public read API with `/public/ping`,
  `last_used_at` stamping on tokens and a structured patient find
  (#345, thanks @lamanji; #358).
- **Notifications: WhatsApp-first channel configuration** with a
  preferred channel per patient, manual send buttons on the patient
  summary and a `GET /notifications/channels` probe so the conversation
  card only renders where WhatsApp is actually available (#310, #287,
  #306, thanks @ZoliQua).
- **Copilot: Anthropic LLM provider adapter**, plus the design brief for
  pluggable free/local providers (#342, #340, #332, thanks @ZoliQua).
- **Polish (`pl`) and Italian (`it`) interfaces** — core app and all 20
  module layers; Polish ships CLDR-exact three-form plural rules (#285,
  #304, #144, #132, thanks @ZoliQua). **German and Hungarian** now cover
  every module layer too (#297, #335), and patient communications
  (email templates, reminders) render in de/hu/pl/it (#344). All nine
  core locales sit at 2489 keys, enforced by a new parity test (#302,
  #312, thanks @lamanji).
- **Flow-continuity batch** (#207): *Confirmar plan* links to its draft
  quote, *Programar cita* preselects the plan's pending treatments, the
  post-appointment dialog can close unmarked treatments and open the
  payment modal in place, and the signature modal prefills the signer
  (#306, thanks @ZoliQua).
- **Onboarding follow-ups** (#205): clinic address in `/setup`, "I see
  patients myself" as a first-class switch, guided mode opens the form
  directly, the guide bar counts the walk and the wizard language
  follows the country preset (#296, thanks @ZoliQua).
- **Agenda: export an appointment as `.ics`** (#282, #129).
- **India GST: GSTIN mod-36 checksum and state-code cross-check**
  (#295, #262).
- **E2E suite runs against a production build in CI** (#294, #259) and
  a country-readiness matrix is tracked in-repo (#339, #146).

### Changed

- **Module system hygiene**: the dependency-debt allowlists are drained
  to empty via provider inversion and seed relocation (#315, #309);
  `appointment_treatments` moved to `treatment_plan` (#338, #337); the
  four import-time registrations moved to `on_activate` with an
  AST-based ADR 0020 guard (#329); five missing module entry points
  declared with a regression guard (#328); Alembic branch-head
  resolution memoized to one walk per process (#336, #323); CI fails
  when a module migrations dir is not registered in `alembic.ini`
  (#346, thanks @lamanji).
- **Baked-but-uninstalled modules stop costing at runtime**: routes
  in `modules.json` plus a module-gate middleware (#333, #326).
- **useApi error contract**: unhandled 4xx responses surface the
  backend's message; silent-failure sweep across error states, input
  preservation and destructive confirms (#317, #311, #101).
- **Accessibility**: aria-labels on all 98 icon-only buttons across
  host and module layers, closing the sweep (#305, #307, #127).
- **Docs**: nine-language READMEs with contributor credits (#313),
  EN/ES user-manual parity (#128), ADR numbering enforced by CI (#303),
  the copilot redaction guarantee stated precisely as pseudonymization
  with a documented free-text gap (#361, #357), Node 22 in CI and BSL
  wording on every README (#363, #352).

### Fixed

- Production deploy hardening (#351): `docker-compose.prod.yml` pulls
  from `ghcr.io/dentalpin/dentalpin-*`, the namespace `release.yml`
  actually publishes to, instead of the stale personal one; the frontend
  image installs with `npm ci` and runs as `node` instead of root; Caddy
  sets HSTS, `X-Content-Type-Options`, `Referrer-Policy` and
  `frame-ancestors 'self'`; `.env.prod.example` pins a release instead of
  `latest` (#362, thanks @lamanji).
- Batch uninstall of a dependency pair no longer strands the dependent
  in `to_remove` (#286): the pending processor now runs removals in
  reverse topological order (dependents first), after installs and
  upgrades, so the dependent's backup runs while its tables still
  exist. Already-dropped tables are detected from the catalog rather
  than `pg_dump`'s stderr (#292, #308).
- Dev compose no longer runs the prod Nitro build, so 4 GB machines boot
  again (#321); the `module_layers` symlink resolves inside the frontend
  container (#293, #261); `frontend/modules.json` is guarded against
  clobbering (#283, #264); Nuxt devtools disabled in e2e (#284).
- Confirmed treatment plans stay schedulable in the appointment
  selector (#301, #108); patient warning flags refresh after saving the
  clinical history (#291, #274); the last local-only full-suite failure
  root-caused and fixed (#316, #188).

## [2.4.0] - 2026-08-24

### Added

- **Eight new optional modules** (all manual-install from the admin UI):
  - **`expenses`** — fixed office cost tracking with date filters,
    pagination and per-role grants (#245, thanks @lamanji).
  - **`lab_orders`** — lab work orders with status tracking; no
    hard-delete, status transitions gated, `received_date` stamped on
    the receive transition (#266, thanks @lamanji).
  - **`medical_reference`** — clinic-managed reference lists for
    allergies, medications, diseases and surgeries, integrated into the
    patient clinical history via slots (#216, thanks @lamanji).
  - **`contacts`** — directory of external labs, suppliers and
    providers (#214, thanks @lamanji).
  - **`patient_relationships`** — patient-to-patient family/guardian
    relationships on the patient summary (#208, thanks @lamanji).
  - **`recall_reminders`** — notifies patients by email when a recall
    is created, with a shipped default template (#189, thanks @lamanji).
  - **`india_gst`** — GST-compliant invoicing for Indian clinics:
    FY-scoped document numbering, turnover-based e-invoice
    applicability, CGST/SGST/IGST breakdown, Tamil PDF output and a
    Tamil Nadu demo fixture (#210, thanks @tresundios).
  - **`integrations`** — outbound webhook subscriptions with outbox
    delivery and API tokens; first trigger is `appointment.completed`
    (#65 Phase 1, PRs #246/#247, thanks @hirad121).
- **German (`de`) and Hungarian (`hu`) interfaces** — full core app,
  2418 keys each, dental-domain terminology reviewed against #131/#275.
  Module-layer keys fall back to English (instead of raw dotted keys)
  until their translations land; the same fallback softens fr/pt/ta
  drift (#276, thanks @ZoliQua).
- **Last-visit smart-card on the patient summary**, fed by a new
  `order=asc|desc` parameter on `GET /appointments` (#182, #251).
- **SSR renders the user's language**: the locale persists in a cookie
  and `Accept-Language` is honoured on first visit (#235, #249).

### Fixed

- **Security: production startup now rejects weak or default
  `SECRET_KEY` values** (GHSA-hcg9-cm67-2g8f, thanks @hirad121).
- **Billing/budget consistency batch**: a treatment plan now owns the
  lines of its linked quote — edits flow one way and conflicting edits
  get a 409 (#176, #177); quotes show and carry net prices per line
  with VAT applied on the discounted base (#181); voiding, deleting or
  crediting an invoice releases the quote lines it consumed (#175); the
  first invoice is no longer blocked for patients with a DNI but no
  billing tax id (#206); invoice PDF footer time, VAT formatting and
  exemption clause corrected (#204); legacy `on_account` allocations
  backfilled into their budget target (#180).
- **Catalog**: price, VAT and status of system treatments are editable
  again (#237), and the treatment modal no longer 422s on mapped
  treatments by sending legacy `visualization_rules`.
- **Reports**: "work completed" derives from fully invoiced quotes
  scoped to the patient (#242); week-glance deltas no longer NaN on
  string decimals (#201).
- **Patients**: `last_visit` counts completed appointments only, and
  the patient list reflects it (#257).
- **UI polish batch** from a fresh-install E2E run (#203) and overlay
  module slots wrapped in `ClientOnly` to stop hydration crashes
  (#258).

## [2.3.1] - 2026-08-20

### Fixed

- **Non-tooth treatments are addable to treatment plans** (#215). Global
  catalog items (limpieza dental, primera visita, radiografía
  panorámica, blanqueamientos, prótesis…) never reached the plan's
  treatment bar: `/catalog/odontogram-treatments` dropped every item
  without an odontogram mapping, and the odontogram service refused to
  create a `Treatment` from unmapped items. The endpoint now returns
  unmapped global-scope items (nullable mapping fields), the service
  falls back to the internal `clinical_type="other"` for global scopes,
  and the "Boca completa" tab groups the ~40 global treatments by
  clinical category with a search filter and an arch picker for
  per-arch items. Demo seeds now write these plan treatments with their
  real scope/arch instead of fake tooth-scoped rows.
- **Patient summary "Diagnoses" card translates clinical types** — it
  pointed at an i18n namespace that never existed, so every label
  rendered as the humanized raw key ("filling composite").

### Added

- **Onboarding: "Treatment catalog" step loads the default catalog inline.**
  The dashboard card's *Set up* opens a dialog with *Load default
  catalog* (VAT, categories and reference treatments for the clinic
  country) or *I will create my own*, instead of only linking to Settings.

## [2.3.0] - 2026-08-18

### Added

- **First-run onboarding redesign** (`/setup`, dashboard "Puesta en
  marcha" card, guided mode, invite links). See
  [`docs/features/onboarding.md`](docs/features/onboarding.md) and
  [ADR 0018](docs/adr/0018-onboarding-seeding-and-state.md).
  - `/setup` asks for the country and derives timezone, currency,
    tax-id format and VAT preset (Spain full preset; generic fallback);
    NIF/CIF checksum warning; UI language switcher in the wizard.
  - `POST /auth/setup` publishes `clinic.created`; catalog, billing,
    agenda and schedules seed their defaults (VAT + catalog, `FAC`/`RECT`
    series, one cabinet, Mon–Fri hours) so the clinic is operative on
    first login.
  - Dashboard card for admins with progress, per-step *Configurar* /
    *Omitir*, inline mini-modals (cabinets, hours, team), optional
    group, *Modo guiado* sticky bar. State stored per clinic in
    `clinic.settings.onboarding` (`PATCH /auth/clinic/settings/onboarding`);
    localStorage dismissal removed.
  - Module getting-started rules: catalog, invoice series, clinic
    hours, SMTP (optional), first patient (optional), VeriFactu
    suggestion for ES (optional).
  - Team invite links without email: `POST /auth/users/{id}/invite-link`
    + public `POST /auth/set-password`; `UserCreate.password` optional;
    `/set-password` page; "access link" row action doubles as an
    admin-driven password reset.
- **Treatment categories can be managed from the UI** (#190).
  Settings → Catalog → *Categorías*: create, rename, reorder,
  deactivate and reactivate. The category CRUD API existed with no
  screen behind it, and the treatment form requires a category, so a
  clinic with none could not create a single treatment.
- **"Load default catalog"** (#190). `POST /catalog/seed` (admin) adds
  the stock VAT types, categories and reference treatments for the
  clinic's country — only what is missing, safe to repeat. Offered in
  the empty state of Settings → Catalog, where the getting-started
  card already sends you. This is the repair path for installs created
  on 2.2.x (which seeded nothing on setup) or where the automatic seed
  failed.
- **Payments: reallocate a collection** from the patient ledger
  ("Asignar a presupuesto…") and pick the destination when recording
  one (`AllocationTargetSelect`), instead of typing a budget UUID (#178).

### Fixed

- **One collection now updates every surface** (#178). Recording a
  payment on an invoice, on a quote or on account converged on
  different tables and never met: invoice payments ignored the
  invoice's budget, quote payments never reached the invoice, refunds
  left the invoice status stale and the patient billing summary
  ignored refunds. Billing now mirrors payment allocations onto the
  budget's open invoices, invoices issued from a quote sweep the
  anticipos already collected (they may be born *paid*), and refunds
  are reflected everywhere. No schema change.
- **Event handlers that silently did nothing** (#183). Handlers that
  opened their own DB session ran before the publisher committed and
  could not see its rows. Two were live production bugs: recall
  auto-link on scheduling had never worked (FK violation swallowed by
  the handler) and the welcome message on patient creation was never
  queued. 23 handlers now run inside the publisher's transaction
  ([ADR 0019](docs/adr/0019-transactional-event-handlers.md)); a CI
  guard fails when a publisher of a transactional event forgets to
  forward its session. Also removes the `SKIP LOCKED` / commit-first
  workarounds that only existed because of the second session, and an
  earned-revenue entry can no longer outlive a treatment whose request
  rolled back.
- **Production frontend image ships every module layer** (#174).
  Modules installed after the image was built (e.g. `accounting_export`
  on the demo) had no page and a raw sidebar label. The prod build now
  bakes all layers; the backend's active-module list decides what is
  visible, and permissions of inactive modules no longer surface
  settings cards.
- **Reactivating a deactivated treatment category** returned 404
  (#190).
- **Nuxt typecheck** of the host app is clean again (8 stale errors);
  the module-layer backlog is tracked in #184.

### Changed

- **Module authoring docs no longer teach "publish after commit"** —
  every module `events.md` states the mode each handler runs in, and
  `creating-modules.md` §6 carries the decision tree and the savepoint
  pattern (#183).

## [2.2.2] - 2026-08-15

### Fixed

- **Quote discounts now reach the treatment plan and the invoice**
  (#167). Reported on the quote → plan → invoice path:
  - Accepting a quote with line and/or global discounts rescales the
    plan's pending sessions to the accepted amounts, so completing a
    session books the discounted price into the patient's earned
    ledger instead of the catalog price. The plan list shows the
    catalog price struck through next to the effective one.
  - Treatments and sessions can no longer be completed while the plan
    is *Draft* or *Pending acceptance* — the API answers 400 and the
    UI hides the action until the plan is *In progress*.
  - Invoices created from a quote now carry the line discount **and**
    the global discount (prorated per line, ex-tax) — the invoice bills
    what the patient signed. Absolute discounts are prorated on partial
    invoicing (no more double charge across two invoices) and can never
    push a line below zero. The from-budget preview matches the
    resulting invoice.
- **Clearing a quote line's discount via the API was ignored.**
  `PUT /budgets/{id}/items/{item_id}` now honours an explicit `null` on
  nullable fields (discount, tooth, surfaces, notes).
- **Appointment hours rendered in the device timezone on mobile.** The
  mobile day view, kanban, home tiles and lists now show clinic
  wall-clock hours on every device, like the desktop grid.

### Added

- **Tamil (ta) UI locale** across the app, email templates and demo
  seeds (#165). Thanks @tresundios.
- **`DEMO_MODE`** — the public demo blocks user edits/removal and module
  install/uninstall/restart so one visitor cannot break it for everyone.

### Changed

- **License**: production use is granted via a standard BSL 1.1
  *Additional Use Grant* (self-hosting and per-client deployments are
  affirmatively permitted; the SaaS restriction is unchanged).

## [2.2.1] - 2026-08-09

### Fixed

- **Plan and quote lifecycles drifted apart on reject/resend/cancel**
  (#162). Three sync gaps reported during functional testing of the
  renegotiation workflow:
  - Reactivating a rejected treatment plan and confirming it again
    never generated a new quote — the plan stayed tied to the old
    rejected one. Re-confirming now provisions a fresh quote and
    relinks the plan (the documented renegotiation flow had the same
    stale-link bug and is fixed too).
  - Accepting a new quote version (the *Resend* flow) did not advance
    the plan: the version chain never carried the plan link. The plan
    now follows the new version, and a plan closed as *rejected by the
    patient* returns to *In progress* automatically when the patient
    accepts the resent quote.
  - Cancelling a quote directly from the Quotes module left the plan
    stuck in *Pending acceptance* forever. The linked plan now returns
    to *Draft*, ready to edit and re-confirm.
- **Reopening a plan whose quote had expired returned a 500.** The
  invalid `expired → cancelled` budget transition is now skipped.
- **Terminal quotes no longer freeze their plan.** Only *sent* or
  *accepted* quotes lock the plan for editing; cancelled, rejected and
  expired ones are history.

### Added

- **"Resend" button on the quote detail page** — clones a rejected,
  expired or cancelled quote into a new draft version (with a fresh
  public link) and navigates to it. Available in all four UI languages.

## [2.2.0] - 2026-08-01

### Added

- **Portuguese (pt-PT) translation.** The fourth UI language after
  Spanish, English and French. Ships the ~2,340-key core locale plus a
  `pt.json` for each of the eleven module layers, so every screen the
  modules contribute is covered too, and the language appears in
  Settings → Account → Language with no further configuration. Patient
  communications can also be switched to Portuguese: the clinic-wide
  communications language accepts `pt` and the full set of transactional
  email templates (appointment confirmation / reminder / cancellation,
  quote sent / accepted, welcome, morning digest, Verifactu alerts) is
  translated. Nuxt UI's own `pt` locale is wired in so date pickers and
  built-in component strings follow. Backend catalog-name resolution
  gained a `pt` fallback, so treatments named in Portuguese resolve on
  invoices, plans, the timeline and the agent tools rather than silently
  falling back to the internal code.

  Not included: the user manual and the demo seed data stay on
  `es/en/fr`, matching how French shipped.

### Fixed

- **Multi-session treatments were charged double.** Completing the last
  step of a multi-session treatment (e.g. an implant with surgery,
  abutment and crown steps) re-recorded the full parent price on top of
  the amounts already charged per session, so a 1,100 € treatment showed
  as 2,200 € owed. Each session now books only its own amount and the
  total always equals the sum of the sessions. The reverse flow is also
  covered: marking the treatment performed from the odontogram charges
  it once in full and auto-cancels its pending sessions. **Upgrading
  repairs affected ledgers automatically** — the migration removes the
  duplicate charges this bug created; no manual action needed.

- Published images were `amd64` only, so `docker compose up` failed at the
  very first command on Apple Silicon and on ARM VPS instances (Hetzner's
  CAX line, the cheapest in Europe and popular with self-hosters) with a
  bare `no matching manifest for linux/arm64/v8`. Each architecture now
  builds on its own native runner and a merge step publishes one manifest
  list per image, verified to carry both before the release is cut.

## [2.1.0] - 2026-07-28

First release cut through the automated pipeline. The eleven modules that
landed since 2.0.0 — payments, copilot, verifactu, recalls, schedules,
notifications, periodontogram, clinical_notes, accounting_export,
migration_import, whatsapp_kapso — are listed per-PR in the generated
release notes and documented in their own module CHANGELOGs; the
narrative version of that work belongs to the next major.

### Added

- **Prebuilt images and a one-command install.** Tagging a release now
  builds and publishes `ghcr.io/dentalpin/dentalpin-backend` and
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
