---
module: treatment_plan
last_verified_commit: 9d3fac6
---

# Treatment Plan — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload |
|-------|------|---------|
| `treatment_plan.created` | Plan created | Consumed by `patient_timeline`. |
| `treatment_plan.status_changed` | Status transition | Currently no subscribers. |
| `treatment_plan.confirmed` | draft → pending | Snapshot payload (items, totals, patient). Subscriber: `patient_timeline`. |
| `treatment_plan.closed` | any → closed | Includes `closure_reason`. Subscriber: `patient_timeline`. |
| `treatment_plan.reactivated` | closed → draft | Subscriber: `patient_timeline`. |
| `treatment_plan.treatment_added` | A `PlannedTreatmentItem` is added to a plan via `POST /treatment-plans/{id}/items`. | `plan_id`, `item_id`, `treatment_id`, `clinic_id`, `patient_id`, `budget_id` (nullable), `catalog_item_id` (nullable), `tooth_number` (nullable), `surfaces` (nullable), `unit_price` (nullable, decimal-as-string), `assigned_professional_id` (nullable, snapshot of the doctor responsible for this line). |
| `treatment_plan.treatment_removed` | Item removed | Includes `budget_id`. Subscriber: `budget`. |
| `treatment_plan.treatment_completed` | Item finalized (all sessions terminal, ≥1 completed) | Audit/recall path only — carries **no price**; earned-ledger generation moved to `item_session_completed` with the multi-session feature. Subscribers: `patient_timeline`, `recalls`. |
| `treatment_plan.item_session_completed` | One session of a plan item marked done (single-session items publish it once on completion) | `plan_id`, `item_id`, `session_id`, `sequence`, `label`, `amount`, `treatment_id`, `patient_id`, `completed_by`, `occurred_at`. Consumed by `payments` (earned row, idempotent on `(treatment_id, session_id)`). |
| `treatment_plan.budget_sync_requested` | Manual resync | Snapshot payload includes full `items[]`. Subscriber: `budget`. |
| `treatment_plan.item_completed_without_note` | Completion check | Consumed by `patient_timeline`. |

**No double booking.** When the last session finalizes the item, the
service calls `TreatmentService.perform(publish_price=False)` so the
resulting `odontogram.treatment.performed` carries `unit_price: null`
— the sessions already booked the money in the payments earned ledger.

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `appointment.completed` | `events.py::on_appointment_completed` | Mark planned items as performed if linked. |
| `budget.accepted` | `events.py::on_budget_accepted` | pending → active (idempotent). |
| `budget.rejected` | `events.py::on_budget_rejected` | pending → closed (`closure_reason=rejected_by_patient`). |
| `budget.renegotiated` | `events.py::on_budget_renegotiated` | pending → draft (budget already cancelled by publisher). |
| `odontogram.treatment.performed` | `events.py::on_treatment_performed` | Mark the matching pending item completed **and cancel its pending sessions** (no session events) — the performed event already carried the full price to payments; a later session completion would book the same money twice. |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
