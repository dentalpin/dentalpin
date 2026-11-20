---
module: agenda
last_verified_commit: 0000000
---

# Agenda — technical overview

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Auto-discovered facts about the `agenda` module. See the module's
own notes at `backend/app/modules/agenda/CLAUDE.md` for context
the scaffold could not infer.

## API surface

- `DELETE /api/v1/agenda/appointments/{appointment_id}`
- `DELETE /api/v1/agenda/cabinets/{cabinet_id}`
- `GET /api/v1/agenda/appointments`
- `GET /api/v1/agenda/appointments/{appointment_id}`
- `GET /api/v1/agenda/appointments/{appointment_id}/cabinet-history`
- `GET /api/v1/agenda/appointments/{appointment_id}/transitions`
- `GET /api/v1/agenda/cabinets`
- `GET /api/v1/agenda/kanban/day`
- `PATCH /api/v1/agenda/appointment-treatments/{appointment_treatment_id}`
- `PATCH /api/v1/agenda/appointments/{appointment_id}/cabinet`
- `POST /api/v1/agenda/appointments`
- `POST /api/v1/agenda/appointments/{appointment_id}/transitions`
- `POST /api/v1/agenda/cabinets`
- `PUT /api/v1/agenda/appointments/{appointment_id}`
- `PUT /api/v1/agenda/cabinets/{cabinet_id}`

## Concurrent writes

Appointment creation, updates and cabinet assignment take a PostgreSQL
transaction-scoped advisory lock per clinic. Other scheduling modules can
import `app.modules.agenda.locks.lock_clinic` and acquire it on the same
session before inspecting availability or writing. The lock serializes
cooperating writers and the existing overlap rules still apply.

## Frontend

- `backend/app/modules/agenda/frontend/pages/appointments/index.vue` → `/appointments`

The appointment editor keeps the stored elapsed duration, including values
outside the standard presets. Its partial update omits start and end times
when the schedule is untouched. Changing just the duration sends a new end time.

## Permissions

`appointments.read`, `appointments.write`, `cabinets.read`, `cabinets.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** _(none)_

module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/agenda/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
