# Schedules module

Clinic + professional operating hours, overrides, availability resolver,
occupancy analytics. **First officially-removable optional module.**
Issue #39, ADR 0002 lessons applied.

## Public API

Routes mounted at `/api/v1/schedules/`.

- `GET  /schedules/clinic-hours`           — `schedules.clinic_hours.read`
- `PUT  /schedules/clinic-hours`           — `schedules.clinic_hours.write`
- `GET  /schedules/professional/{id}`      — `schedules.professional.read` / `professional.own.read`
- `PUT  /schedules/professional/{id}`      — `schedules.professional.write` / `professional.own.write`
- `GET  /schedules/availability`           — `schedules.availability.read`. Consumed by agenda's frontend; **404-tolerant** (agenda falls back to legacy 08:00–21:00 bounds when the module is uninstalled).
- `GET  /schedules/analytics/occupancy`    — `schedules.analytics.read`

## Dependencies

`manifest.depends = ["agenda"]`. Schedules **reads** appointment data
to compute occupancy, but **agenda must NEVER declare
`depends: ["schedules"]`** — that would make schedules required and
defeat the uninstall story. Integration goes the other way: agenda's
frontend calls `/api/v1/schedules/availability` with a fallback.

## Permissions

`schedules.clinic_hours.{read,write}`,
`schedules.professional.{read,write}`,
`schedules.professional.own.{read,write}`,
`schedules.availability.read`,
`schedules.analytics.read`.

## Tools exposed

Agent tool in `tools.py` (wraps `AvailabilityService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `get_availability` | READ | `AvailabilityService.resolve` | `schedules.availability.read` |
| `find_free_slots` | READ | `AvailabilityService.resolve` + agenda appointments | `schedules.availability.read` + `agenda.appointments.read` |

`get_availability` returns **open working windows** for a day (not gaps
minus appointments). `find_free_slots` does the real thing: it subtracts
the professional's booked appointments from those windows and returns the
**contiguous free windows** as `free_windows` (each with real `start`,
`end` and `minutes`), nearest first, filterable by minimum duration
(`slot_minutes`) / part-of-day / window. Returning the true extent of each
gap (not fixed-size slots) lets the agent know whether a hole is 9:00–9:30
or 9:00–18:00. It reads agenda appointments directly — allowed because
`agenda` is in `manifest.depends`.

## Events emitted

None today.

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `appointment.scheduled` | `on_appointment_scheduled` | Recompute occupancy aggregates |
| `appointment.updated`   | `on_appointment_updated`   | Recompute occupancy aggregates |
| `appointment.cancelled` | `on_appointment_cancelled` | Free the slot in occupancy aggregates |

See `events.py`.

## Frontend integration

Settings UI is contributed via the host's settings registry, not via
file-based routes. The client plugin
`frontend/plugins/settings.client.ts` calls `registerSettingsPage(...)`
twice to mount cards/pages under `/settings/workspace`:

| Path | Component | Permission gate |
|---|---|---|
| `clinic-hours` | `components/settings/ClinicHoursPage.vue` | `schedules.clinic_hours.read` |
| `professional-schedules` | `components/settings/ProfessionalSchedulesPage.vue` | canAny `professional.read` ∪ `professional.own.read` |

The host's `[category]/[page].vue` route mounts the registered
component, applies auth middleware, and renders title/subtitle from
the i18n keys. The page components contain only domain UI — no outer
container, h1, or auth boilerplate.

The plugin imports the registry from `~~/app/composables/...` (host
shell), not from another module, so `manifest.depends` stays at
`["agenda"]`.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- `uninstall()` drops schedules tables; agenda continues to function
  via its frontend's 404-tolerant availability composable.
- Migrations on the `schedules` Alembic branch — see ADR 0002.

## Gotchas

- **Direction of integration.** Agenda must not import or depend on
  schedules. The data flow is one-way: schedules consumes agenda's
  events; agenda's UI calls schedules' HTTP endpoint with a fallback.
- **Occupancy is a derived view.** Source of truth for appointments
  stays in agenda. Don't write back into agenda from here.
- **Removable invariant.** Any new code in this module must keep the
  uninstall round-trip green (`backend/tests/test_uninstall_roundtrip.py`).
- **Shifts of one day never overlap.** The weekly and override schemas
  reject overlapping shifts with a 422 (touching 09–14 / 14–18 is fine),
  and `_sorted_shifts` merges any overlap already stored: the range
  builder walks a cursor forward, and a shift inside another used to paint
  the rest of the day closed while the analytics counted the inner shift's
  minutes twice (#991).
- **Analytics permission.** Receptionists read analytics; hygienists
  do not. Don't widen.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
