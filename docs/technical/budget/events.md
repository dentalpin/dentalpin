---
module: budget
last_verified_commit: 6c91240
---

# Budget — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload |
|-------|------|---------|
| `budget.sent` | Budget marked as sent (email or manual delivery). | `budget_id`, `clinic_id`, `patient_id`, `budget_number`, `plan_id` (nullable), delivery metadata. |
| `budget.accepted` | Patient (public link) or staff (in-clinic) accepts and signs. | Snapshot incl. `accepted_via`, `total`, `plan_id` (nullable) and `items[]` — one entry per line: `budget_item_id`, `treatment_id` (nullable), `catalog_item_id`, `quantity`, `net_amount` (ex-tax, after line discount + prorated global discount via `pricing.allocate_global_discount`; issue #167). Subscribers: `treatment_plan` (pending → active; closed-as-rejected → active; reprices pending sessions from `items[].net_amount`), `patient_timeline`, `notifications`. |
| `budget.rejected` | Patient or staff rejects. | Snapshot incl. `rejection_reason`, `plan_id` (nullable). Subscriber: `treatment_plan` (pending → closed). |
| `budget.expired` | Daily cron, `valid_until < today` while draft/sent. | Snapshot incl. `days_overdue`, `plan_id`. |
| `budget.renegotiated` | `POST /budgets/{id}/renegotiate` cancels a sent budget for renegotiation. | `budget_id`, `plan_id` (nullable), `patient_id`, `version`, `cancelled_at`, `cancelled_by`. Subscriber: `treatment_plan` (pending → draft). |
| `budget.cancelled` | `POST /budgets/{id}/cancel` — staff cancels directly (issue #162). **Not** published when the cancel is initiated by `treatment_plan.reopen()` (`publish_event=False`) — the plan module owns that transition and an echo would deadlock. | `clinic_id`, `budget_id`, `patient_id`, `budget_number`, `plan_id` (nullable), `reason`, `cancelled_by`, `occurred_at`. Subscriber: `treatment_plan` (pending → draft). |
| `budget.superseded` | `POST /budgets/{id}/resend` clones a terminal (rejected/expired/cancelled) budget to a new draft version (issue #162). **Published after the request transaction commits** — sole deviation from the pre-commit pattern; the subscriber points an FK at the new row, which is invisible pre-commit. | `clinic_id`, `budget_id` (old), `new_budget_id`, `patient_id`, `plan_id`, `version` (new), `resent_by`, `occurred_at`. Subscriber: `treatment_plan` (repoints `budget_id`). |
| `budget.viewed` | Patient opens the public link (first time, idempotent). | `budget_id`, `plan_id`, `patient_id`, `viewed_at`, `ip_hash`. |
| `budget.reminder_sent` | Automatic reminder milestone (7d / 14d). | `budget_id`, `plan_id`, `patient_id`, `milestone_days`, `sent_at`. |

`plan_id` is resolved by reverse raw-SQL lookup
(`BudgetWorkflowService._lookup_plan`) — never by importing
treatment_plan models (ADR 0003). It is `null` for standalone budgets.

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `odontogram.treatment.performed` | `__init__.py` → `BudgetService.on_treatment_performed` | Mark matching line items done. |
| `treatment_plan.budget_sync_requested` | `__init__.py::_on_sync_requested` | Rebuild draft-budget lines from the snapshot payload. |
| `treatment_plan.treatment_added` | `__init__.py::_on_treatment_added_to_plan` | Add matching line to the linked draft budget (no-op on non-draft). |
| `treatment_plan.treatment_removed` | `__init__.py::_on_treatment_removed_from_plan` | Remove matching line from the linked draft budget. |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
