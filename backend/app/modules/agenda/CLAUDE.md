# Agenda module

Appointments, scheduling, cabinets. Owns the `Appointment` entity and
its state machine.

## Public API

Routes mounted at `/api/v1/agenda/`. See `router.py` for the full
surface (appointments CRUD, transitions, cabinet assignments, kanban).

**QR check-in.** Staff mints a signed 15-minute token per appointment
(`POST /appointments/{id}/check-in-token`, returns the token plus the
patient-facing URL built server-side from `ALLOWED_ORIGINS`);
`GET .../check-in-qr` renders the same URL as PNG. Patients consume it
unauthenticated at the agenda-owned `/p/check-in/<token>` page via
`POST /public/check-in/{token}` (per-IP + per-token limits,
`note="qr-checkin"`), through the canonical status machine.

## Dependencies

`manifest.depends = ["patients", "catalog", "odontogram"]`.

**Planned-work contract (#309/#337).** Booking against treatment-plan
items is a two-way product dependency, but ``treatment_plan`` already
declares ``agenda`` and the manifest graph must stay acyclic — so this
module NEVER imports treatment_plan. It owns the
``PlannedWorkProvider`` protocol + registry in ``planned_work.py``;
``treatment_plan`` registers its implementation from ``on_activate``
(``agenda_provider.py``). Since #337 the ``appointment_treatments``
table and its ``AppointmentTreatment`` model are treatment_plan-owned
too (the planned-item FK is NOT NULL — it was always the plan's visit
bridge): the provider installs ``Appointment.treatments`` via backref,
serves the full eager-load options, creates the link rows at booking,
and hands agenda the clinic-scoped row for the visit-note editor.
Agenda touches the rows only duck-typed. The FK allowlist in
``tests/test_module_fk_isolation.py`` is empty.

## Permissions

`agenda.appointments.{read,write}`, `agenda.cabinets.{read,write}`.

## Tools exposed

Agent tools in `tools.py` (wrap `AppointmentService`, no logic duplicated).
Write tools use `ctx.supervisor_id` (the human in the loop) for audit columns.

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `get_day_overview` | READ | `AppointmentService.list_appointments` | `agenda.appointments.read` |
| `get_appointment` | READ | `AppointmentService.get_appointment` | `agenda.appointments.read` |
| `list_cabinets` | READ | `CabinetService.list_cabinets` | `agenda.cabinets.read` |
| `list_professionals` | READ | `kanban_service._fetch_professionals` | `agenda.appointments.read` |
| `book_appointment` | WRITE | `AppointmentService.create_appointment` | `agenda.appointments.write` |
| `reschedule_appointment` | WRITE | `AppointmentService.update_appointment` | `agenda.appointments.write` |
| `update_appointment_status` | WRITE | `AppointmentService.transition` | `agenda.appointments.write` |
| `cancel_appointment` | DESTRUCTIVE | `AppointmentService.cancel_appointment` | `agenda.appointments.write` |

`update_appointment_status` excludes `cancelled` (that's `cancel_appointment`,
DESTRUCTIVE). Invalid transitions return the allowed next states from
`VALID_TRANSITIONS` so the agent can self-correct instead of retry-looping.

`find_free_slots` is intentionally **not** here — free-slot computation belongs to
`schedules`, which will register its own tool. Agenda does not cross that boundary.

## Frontend slots exposed

- `appointment.completed.followup` — rendered by `AppointmentQuickActions.vue`
  after a successful transition to `completed`. Sibling modules
  (e.g. `recalls`) register components that prompt the receptionist
  for a follow-up action. Modal stays hidden when no registrations
  exist. Slot ctx: `{ appointment }`.

## Events emitted

- `appointment.scheduled` — new appointment
- `appointment.updated` — generic update
- `appointment.status_changed` — published alongside specific status events; payload carries `from_status`/`to_status`/`changed_at`/`changed_by`
- `appointment.cabinet_changed` — cabinet (re)assignment, payload includes `from_cabinet_id`/`to_cabinet_id` (nullable)
- `agenda.visit_note_updated` — visit-level note (reuses `AppointmentTreatment.notes`)

## Events consumed

None.

## Lifecycle

- `removable=False`. Most modules depend on appointments.

## Gotchas

- **Datetime semantics (issue #161).** Naive `start_time`/`end_time`
  entering the module (payloads, filters) are **clinic-local wall-clock**
  (`clinics.timezone`); aware values are instants. Storage is UTC; API
  responses serialize both fields **with the clinic offset** via
  `router._localize` (audit timestamps stay UTC). Helpers in `tz.py` —
  don't hand-roll conversions, and never compare naive vs stored values.
  **Frontend:** anything that shows an hour or buckets by day reads the
  clinic wall-clock via `parseWallClock()` / `clinicNow()` from
  `~~/app/utils/wallClock` (or slices the ISO string) — never
  `new Date(iso).getHours()`/`toLocaleTimeString()`, which re-render the
  instant in the *device's* timezone (mobile showed 13:00 for a 12:00
  appointment on a phone one hour ahead of the clinic). Instant math
  (sorting, overlap, "starts in N min", timers) keeps using `new Date`.

- **Schedules must NOT be a dependency.** The `schedules` module depends
  on agenda; the data flow is one-way. Never declare
  `depends: ["schedules"]` here. See `schedules/CLAUDE.md`.
- **Status transitions go through `AppointmentService.transition`** —
  it publishes both the specific status event and the generic
  `appointment.status_changed`.
- **Cabinet assignment uses `assign_cabinet`** — it publishes
  `appointment.cabinet_changed` with both old and new ids.
- **Mobile free-slot computation is client-side** (#61). The composable
  `frontend/composables/useFreeSlots.ts` derives gaps from already-loaded
  appointments + the optional `schedules` availability payload. Do not
  add a backend free-slot endpoint without ADR — the data flow stays
  client-side and the schedules dependency stays optional.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
