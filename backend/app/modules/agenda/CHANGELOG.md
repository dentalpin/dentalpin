# Changelog — agenda module

## Unreleased

- feat(#287): the appointment modal's email-only confirmation checkbox and mail dropdown are replaced by channel-aware controls driven by the clinic's manual channels (confirmation/reminder/cancellation per receivable channel).

- fix(#101): a failed appointments fetch renders an error banner with Retry instead of a blank calendar that reads as a free week; the appointment modal's footer cancel now asks for confirmation.

- feat(#207): the appointments page forwards `?plan_id=` to the create modal (`initialPlanId`), which preselects that plan's pending treatments in the treatment selector.

- fix(#108): `validate_planned_items` accepts items from `pending` plans (plan confirmed, quote not yet accepted). It only ever allowed `active`+`draft`, so once the appointment selector started offering `pending` plans the booking failed on save with `Treatment item ... belongs to pending plan`. Terminal plans (`completed`/`closed`) stay rejected, and completion is still gated on `active` — booking ahead of the acceptance is allowed, invoicing against it is not. First test coverage for this gate (`tests/test_appointment_planned_items.py`).

- feat(#129): `GET /agenda/appointments/{id}.ics` — export one appointment as an RFC 5545 iCalendar file (UTC timestamps, CRLF + 75-octet folding, escaped text values, stable `UID` of `<appointment-uuid>@dentalpin.com`, `text/calendar` attachment). Hand-rolled builder in `ics.py`, no new dependency. Registered before the plain `/{id}` route so the `.ics` suffix isn't swallowed by the UUID param.

- fix(#203): the kanban card menu trigger carried `aria-label="Marcar llegada"` in every column; now the neutral `appointments.actionsMenu` ("Acciones de la cita"), added to all five locales.

- feat: `GET /agenda/appointments` accepts `order=asc|desc` (by `start_time`, default `asc`). `LastVisitCard` now fetches the most recent completed visit with a single `order=desc&page_size=1` request instead of paging to the tail (PR #251 follow-up).

- feat(#182): `LastVisitCard` on `patient.summary.cards` (order 21, next to the next-appointment card) — shows the patient's most recent completed appointment (date/time/professional/treatment) with an explicit "Sin visitas previas" empty state, so reception can tell a first-timer from a regular on the Resumen tab. Click opens the appointment on the agenda, or the agenda with the patient pre-selected when there is none.

- fix(#184): type-check clean. `useAppointments`/`useHomeAgenda` expose their lists with `shallowReadonly` (the deep `readonly()` view forced `DeepReadonly<Appointment>` through every child prop); the mobile day summary/timeline called `t()` with a 3-arg (key, fallback, params) form vue-i18n does not have — the keys exist in every locale, so params only; `getCabinetColor` accepts the nullable cabinet; the modal no longer sends a `media` field `PlannedTreatmentItem` does not have.
- fix(#183): appointment events are published with `db=` so recalls, treatment_plan and notifications react inside the request's transaction (ADR 0019).
- feat(onboarding): subscribe to `clinic.created` — create one default cabinet for a new clinic.

- fix(timezones): the mobile day view (free-slot engine, timeline,
  week-strip counts), kanban card labels, home tiles, next-appointment
  card and list view formatted appointment hours with `new Date()`
  — i.e. in the *device's* timezone — while the desktop grid renders
  clinic wall-clock. On a phone in a different zone than the clinic
  the same appointment showed a different hour (12:00 vs 13:00) and
  tapping a free slot booked it at the shifted hour. All hour/day
  rendering now goes through `parseWallClock()` / `clinicNow()`
  (`frontend/app/utils/wallClock.ts`); instant math is unchanged.

- fix(timezones): appointment times entered as naive clinic-local
  wall-clock were persisted unconverted as UTC, so the dashboard
  (which parses instants with `new Date()`) showed them shifted by
  the clinic's UTC offset — e.g. 11:00 → 06:00 in America/Lima
  (issue #161). Naive datetimes (create/update payloads, list
  filters, `get_day_overview` bounds) are now interpreted in
  `clinics.timezone` and stored as UTC; API responses serialize
  `start_time`/`end_time` with the clinic offset so both wall-clock
  consumers (calendar string slicing) and instant consumers agree.
  Kanban day windows are computed in the clinic timezone too. Data
  migration `ag_0006` reinterprets existing rows per clinic.

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(ui): surface the API error instead of a generic toast in the appointment modal and the kanban board (transition, cabinet assign) plus the unconfirmed panel.
  `catch {}` discarded the server's message, so any failure read as
  "Error" with no way to tell what went wrong. Now via
  `errorMessage()` / `errorDetail()`.

- fix(professionals): the professionals listing (kanban) and
  `validate_professional_access` now check
  `ClinicMembership.is_professional` instead of `role IN (dentist,
  hygienist)`, so an admin who also practises can hold appointments
  (core migration 0006; Telegram report, 2026-07-31).

- feat(agents): two new copilot tools — `reschedule_appointment` (WRITE,
  wraps `AppointmentService.update_appointment`, surfaces `slot_conflict`
  as a structured error) and `update_appointment_status` (WRITE, wraps
  `transition`; invalid transitions return the allowed next states;
  `cancelled` stays exclusive to the DESTRUCTIVE `cancel_appointment`).

- fix(agenda): the appointments page now refetches its active window when
  the shared client data bus signals an `agenda` change (e.g. a copilot
  booking/cancellation), so externally created appointments appear without a
  manual reload. Deduped the post-save/cancel reload into `reloadActiveView`.

- fix(modal): show the correct duration when editing an appointment. The
  `selectedTreatments` watcher recomputed `formData.duration` from a
  treatment-count heuristic and clobbered the value derived from the
  appointment's start/end times during initial edit-mode population. Gated
  the watcher behind `initialDataLoaded` so only user-driven treatment
  changes adjust the duration.
- feat(agents): expose `tools.py` for the copilot agentic layer —
  `get_day_overview` (READ), `book_appointment` (WRITE),
  `cancel_appointment` (DESTRUCTIVE). Thin wrappers over
  `AppointmentService`; clinic-scoped; RBAC via existing
  `agenda.appointments.*`. `find_free_slots` deferred to `schedules`.
  Issue #81 Layer B.
- feat(agents): add `get_appointment` (READ) and `list_cabinets` (READ)
  tools. Issue #81 P0 batch.
- feat(agents): add `list_professionals` (READ) — resolves a
  professional name → id (reuses `kanban_service._fetch_professionals`).
  Staff names returned under `professional_name` (outside the redactor
  PII set) so name resolution works. Issue #81 P1 batch.

- fix(modal): suppress spurious "Se detectaron solapamientos" toast
  after creating an appointment. ``useAppointments.createAppointment``
  mutates the shared ``appointments`` array (same reactive instance the
  parent passes as ``existingAppointments``), so the just-created entry
  briefly self-overlapped with ``formData`` before the modal closed and
  the overlap watcher fired against it. Fix flips
  ``initialDataLoaded`` off at the top of ``handleSave`` — the same
  flag the modal already uses when closing — so the watcher stays quiet
  until the modal reopens.
- fix(modal-tz): "Este slot está fuera del horario" no longer fires
  for in-hours slots when the browser timezone differs from the clinic
  timezone (e.g. Madrid receptionist on an NY clinic). The pre-save
  availability check compared instants — naive form strings interpreted
  as browser-local against ``r.start``/``r.end`` carrying the clinic
  offset — which shifted the slot by the browser↔clinic gap. Now
  compares wall-clock minutes via ``parseIsoParts`` /
  ``isoPartsToDateKey``, mirroring ``useCalendarBounds`` /
  ``useBlockedSegments``.
- feat(notes)!: appointment notes promoted to the polymorphic
  ``clinical_notes`` store. The legacy free-text
  ``appointments.notes`` column is **dropped** (``ag_0005``); the
  ``Notes`` section of ``AppointmentModal`` becomes an
  ``appointment.detail.notes`` slot that ``clinical_notes`` fills with
  ``AppointmentNotesPanel`` (Clínica + Administrativa buttons +
  cronological feed). Patient-facing email templates stop carrying
  the free-text ``notes`` context key (it was internal-only by intent).
  Migration is pre-prod: no data backfill — reset dev with
  ``./scripts/reset-db.sh && ./scripts/seed-demo.sh``.
- feat(ux): `AppointmentModal` header now exposes an "Abrir ficha"
  link next to the selected patient's name. Closes the modal and
  navigates to `/patients/{id}` so receptionists/dentists can jump
  to the clinical record without first cancelling the modal and
  searching the patients list. Gated by `patients.read`; hidden
  when no patient is selected yet.
- fix(calendar-tz): ``useCalendarBounds`` and ``useBlockedSegments``
  now parse the wall-clock hour from the availability ISO string
  verbatim instead of routing it through ``new Date().getHours()``,
  which silently re-interpreted the timestamp in the browser timezone.
  Symptom: a clinic configured for ``9–14, 16–20`` in NY served to a
  Madrid browser rendered as a single ``15–20`` block (morning shift
  shifted into the afternoon, afternoon shift crossed midnight and was
  clipped). Hours are now always clinic-local regardless of browser TZ.
- fix(filters): the professional filter chip strip now scrolls
  horizontally instead of wrapping. With 50+ dentists the wrapped
  rows pushed the calendar grid below the fold, leaving only the
  afternoon visible. The chip strip is now bounded to one row with
  an ``overflow-x-auto`` track; the calendar reclaims its height.
- feat(ux): receptionist can create a new patient inline from the *Nueva cita* modal. The patient selector dropdown surfaces a ``+ Crear paciente "<query>"`` row when the typed name doesn't match an existing record; clicking it opens a 3-field mini-form (nombre, apellidos, teléfono) that POSTs to ``/api/v1/patients`` and auto-selects the created patient. Closes the 30-second "patient on the phone" workflow. See ``docs/features/agenda-quick-patient-create.md`` and ``docs/technical/agenda-quick-patient-create.md``.
- perf(scheduler): replace ``AppointmentDailyView`` overlap-grouping loop with a union-find DSU (extracted to ``composables/calculateOverlapGroups.ts``); pre-bucket appointments by professional once; switch the per-column template ``v-for`` to a Map lookup and add ``v-memo`` so dragging an appointment no longer re-renders the other columns.
- perf(scheduler): ``useBlockedSegments`` now fetches per-professional availability in parallel via ``Promise.all`` (was sequential ``for…of``).
- perf(bundle): wrap ``AppointmentCalendar`` / ``AppointmentDailyView`` / ``AppointmentKanbanView`` / ``AppointmentMobileDayView`` in ``defineAsyncComponent``; the initial ``/agenda`` payload only ships the active mode for the current viewport.
- refactor(dx): extract ``formatLocalDate`` to ``utils/date.ts`` and remove the five duplicate copies across agenda components and the page; new ``frontend/tests/agenda/calculateOverlapGroups.test.ts`` pins the DSU output against fixtures.
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast pattern in ``useAppointments`` now that ``useApi`` accepts ``object`` payloads directly.
- refactor(perms): migrate the hardcoded ``can('agenda.appointments.write')`` gate in ``UnconfirmedPanel`` to ``PERMISSIONS.appointments.write``.
- fix(isolation): declare ``odontogram`` in ``manifest.depends``. The
  service already imported ``Treatment`` to render appointment
  treatments — the dependency was real, just undeclared.
  ``KNOWN_VIOLATIONS`` allowlist trimmed accordingly.
  (``treatment_plan`` stays as a legit known violation because
  treatment_plan depends on agenda — declaring would cycle.)
- fix(isolation): ``Appointment.patient`` no longer uses
  ``back_populates="appointments"`` — the matching attribute was
  removed from the foundational ``patients`` module. The
  relationship stays one-directional (Appointment → Patient); code
  that needs the reverse side queries agenda directly.
- perf(appointments-list): count query now hits the same indexed
  filters directly instead of materialising a subquery — drops the
  list endpoint from O(rows × eager-load tree) to O(rows) once a
  clinic crosses ~10k appointments.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).
- **Slot uniqueness now ignores terminal statuses.** Migration
  `ag_0004` rebuilds the partial unique index
  `idx_appointment_slot` with
  `WHERE status NOT IN ('cancelled', 'completed', 'no_show')`.
  Previously the index excluded only `cancelled`, so a finished
  visit kept reserving its `(clinic, cabinet, professional,
  start_time)` slot and a fresh checked-in appointment couldn't
  be assigned to that cabinet. Slot competition now only applies
  among truly active statuses.
- New frontend slot mount **`appointment.completed.followup`** in
  `AppointmentQuickActions.vue` (issue #62). After a successful
  transition to `completed`, agenda renders a follow-up modal whose
  body is filled by any sibling module registered into the slot
  (e.g. `recalls` "Schedule a recall?" prompt). Modal stays hidden
  when no module has registered into the slot — no behaviour change
  for clinics that don't install recalls.

- Week view (`AppointmentCalendar`) now paints `clinic_closed` ranges per
  day as a hatched overlay, matching the daily view. Late-start mornings,
  early-close evenings, midday gaps and fully-closed days are all
  visually blocked instead of looking bookable. Slot math extracted into
  the new `useBlockedSegments` composable; daily view refactored to use
  it, dropping inline duplication.
- `GET /api/v1/agenda/appointments` now accepts a `patient_id` filter.
  Previously the patient-detail Citas tab passed `patient_id` but the
  endpoint silently ignored it and returned the whole clinic's
  appointments. `AppointmentService.list_appointments` gained a
  keyword-only `patient_id` argument.
- Patient detail → Clínica → Citas: `AppointmentsMode` paginates with
  the shared `PaginationBar` at page_size=20, dropping the hard-coded
  page_size=100 single-page dump.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Mobile agenda: surface free slots for quick emergency booking (#61).
  - New composable `useFreeSlots` computes busy/free/blocked timeline
    entries client-side from appointments + schedules availability.
  - New components `AppointmentMobileTimeline` and
    `AppointmentMobileDaySummary`. Single-track UX (one professional or
    one cabinet at a time), persisted in `localStorage`.
  - Min-duration filter chips (15/20/30/45/60+) hide noisy short gaps;
    short gaps render as faded pills.
  - Free-slot tap pre-fills the appointment composer with start time,
    duration and resource (professional or cabinet).
  - `AppointmentModal` now takes an optional `initialCabinet` prop and
    renders fullscreen on mobile with larger tap targets.

## 0.4.0 — initial documented version

- Appointment CRUD with full state machine.
- Cabinet assignment with `appointment.cabinet_changed` events.
- Visit-level notes via `AppointmentTreatment`.
- Kanban view backed by `kanban_service`.
