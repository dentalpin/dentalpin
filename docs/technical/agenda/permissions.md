---
module: agenda
last_verified_commit: 76b1273
---

# Agenda — permissions

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Returned by `AgendaModule.get_permissions()`
(relative names; the registry namespaces them as `agenda.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `agenda.appointments.read` | View appointments and export them. | `GET /agenda/appointments`, `GET /agenda/appointments/{appointment_id}`, `GET /agenda/appointments/{appointment_id}.ics` (RFC 5545 export, #129) |
| `agenda.appointments.write` | Create and edit appointments, mint QR check-in tokens and render QR images. | Appointment CRUD and transitions, `POST /agenda/appointments/{appointment_id}/check-in-token`, `GET /agenda/appointments/{appointment_id}/check-in-qr` |
| `agenda.cabinets.read` | _Describe what this allows._ | _List the endpoints._ |
| `agenda.cabinets.write` | _Describe what this allows._ | _List the endpoints._ |

Unauthenticated (no permission): `POST /agenda/public/check-in/{token}`
consumes a signed 15-minute token through the canonical status machine
(rate-limited per IP and per token).

## Role assignment

See `backend/app/core/auth/permissions.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/agenda/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
