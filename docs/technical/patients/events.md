---
module: patients
last_verified_commit: 0e9a0ac
---

# Patients — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | Source | When | Payload |
|-------|--------|------|---------|
| `patient.created` | `service.py:PatientService.create` | After insert + extended row commit. | `patient_id` (UUID), `clinic_id` (UUID) |
| `patient.updated` | `service.py:PatientService.update` | After partial update commit. | `patient_id` (UUID), `changes` (dict of changed fields) |
| `patient.archived` | `service.py:PatientService.archive` | After soft-delete (status → archived). | `patient_id` (UUID) |
| `patient.restored` | `service.py:PatientService.restore` | After restore (status → active). Reverses the media archive cascade. | `patient_id` (UUID), `clinic_id` (UUID) |

Subscribers are listed in the auto-generated [events catalog](../../events-catalog.md).

## Subscribed

This module does not subscribe to any events.

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method after `flush()` — the bus runs handlers
   inline, *before* the request commits. Pass `db=db` so transactional
   subscribers can join the transaction (ADR 0019, issue #183).
3. Add a row to the table above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the global
   catalog.
