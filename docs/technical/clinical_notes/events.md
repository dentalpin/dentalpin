---
module: clinical_notes
last_verified_commit: 50cce0f
---

# Clinical-notes — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

One event per note type. The publish call passes a variable resolved
from the `_NOTE_TYPE_TO_EVENT` map in `service.py`, so the catalog
attributes these from the `EventType` constants referenced in that file.

| Event | When | Consumers |
|-------|------|-----------|
| `clinical_notes.diagnosis_created` | A diagnosis note is created | patient_timeline |
| `clinical_notes.treatment_created` | A treatment note is created | patient_timeline |
| `clinical_notes.plan_created` | A treatment-plan note is created | patient_timeline |
| `clinical_notes.administrative_created` | An administrative note is created | patient_timeline |
| `clinical_notes.appointment_clinical_created` | A clinical note captured on an appointment | patient_timeline |
| `clinical_notes.appointment_administrative_created` | An administrative note captured on an appointment | patient_timeline |

Payloads carry `clinic_id`, `patient_id`, and a `body_excerpt`. For
appointment notes `patient_id` is the appointment's patient, so the
timeline row lands on that patient's ficha (#1155).

## Subscribed

_This module does not subscribe to any events_ (`get_event_handlers`
returns `{}`).

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method after `flush()` — the bus runs handlers
   inline, *before* the request commits. Pass `db=db` so transactional
   subscribers can join the transaction (ADR 0019, issue #183).
3. Add the row to the table above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
