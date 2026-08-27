---
module: patient_timeline
last_verified_commit: 0000000
---

# Patient Timeline — events

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

_This module does not publish any events._

## Subscribed

Every handler goes through `events.py::_record` and is deliberately
**own-session and payload-only** (ADR 0019, issue #183): the timeline
records what the payload carries, never re-reads the publisher's rows, and
must never be able to fail the event it is logging.

| Event | Handler | Effect |
|-------|---------|--------|
| `agenda.visit_note_updated` | _Handler module path._ | _What it does in response._ |
| `appointment.cancelled` | _Handler module path._ | _What it does in response._ |
| `appointment.checked_in` | _Handler module path._ | _What it does in response._ |
| `appointment.completed` | _Handler module path._ | _What it does in response._ |
| `appointment.confirmed` | _Handler module path._ | _What it does in response._ |
| `appointment.in_treatment` | _Handler module path._ | _What it does in response._ |
| `appointment.no_show` | _Handler module path._ | _What it does in response._ |
| `appointment.scheduled` | _Handler module path._ | _What it does in response._ |
| `budget.accepted` | _Handler module path._ | _What it does in response._ |
| `budget.expired` | _Handler module path._ | _What it does in response._ |
| `budget.rejected` | _Handler module path._ | _What it does in response._ |
| `budget.reminder_sent` | _Handler module path._ | _What it does in response._ |
| `budget.renegotiated` | _Handler module path._ | _What it does in response._ |
| `budget.sent` | _Handler module path._ | _What it does in response._ |
| `budget.viewed` | _Handler module path._ | _What it does in response._ |
| `clinical_notes.administrative_created` | _Handler module path._ | _What it does in response._ |
| `clinical_notes.diagnosis_created` | _Handler module path._ | _What it does in response._ |
| `clinical_notes.plan_created` | _Handler module path._ | _What it does in response._ |
| `clinical_notes.treatment_created` | _Handler module path._ | _What it does in response._ |
| `document.uploaded` | _Handler module path._ | _What it does in response._ |
| `notification.failed` | `events.on_notification_failed` | Timeline row for a failed outbound send, any channel (#287 bug 12; replaces the legacy `email.failed` subscription). |
| `notification.sent` | `events.on_notification_sent` | Timeline row for an outbound send, any channel (replaces the legacy `email.sent` subscription — the gateway dual-publishes both for email, so subscribing to both would double-record). |
| `invoice.issued` | _Handler module path._ | _What it does in response._ |
| `invoice.paid` | _Handler module path._ | _What it does in response._ |
| `media.pair_created` | _Handler module path._ | _What it does in response._ |
| `media.photo_uploaded` | _Handler module path._ | _What it does in response._ |
| `odontogram.treatment.performed` | _Handler module path._ | _What it does in response._ |
| `patient.medical_updated` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.closed` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.confirmed` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.created` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.item_completed_without_note` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.reactivated` | _Handler module path._ | _What it does in response._ |
| `treatment_plan.treatment_completed` | _Handler module path._ | _What it does in response._ |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method after `flush()` — the bus runs handlers
   inline, *before* the request commits. Pass `db=db` so transactional
   subscribers can join the transaction (ADR 0019, issue #183).
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
