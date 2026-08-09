---
module: treatment_plan
screen: detail
route: /treatment-plans/[id]
related_endpoints:
  - DELETE /api/v1/treatment_plan/treatment-plans/{plan_id}
  - DELETE /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}
  - GET /api/v1/treatment_plan/treatment-plans
  - GET /api/v1/treatment_plan/treatment-plans/patient/{patient_id}
  - GET /api/v1/treatment_plan/treatment-plans/pipeline
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/complete
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/status
  - POST /api/v1/treatment_plan/treatment-plans
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/close
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/confirm
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/contact-log
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/generate-budget
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/items
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/link-budget
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/reactivate
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/reopen
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/sync-budget
  - PUT /api/v1/treatment_plan/treatment-plans/{plan_id}
  - PUT /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
  - treatment_plan.plans.confirm
  - treatment_plan.plans.close
  - treatment_plan.plans.reactivate
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatment-plans/[id].vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: 2a05d7a
---

# Treatment plan detail

Plan view: header with patient, professional, and status; main
column with the items (catalog or odontogram tooth treatment); and
sidebar with the linked budget, executions, and contacts. This is
where you confirm, sync with the budget, mark items as performed,
and close or reactivate.

## At a glance

- **Status chip.** The header chip reflects the state: `draft`,
  `pending`, `active`, `completed`, `closed`. Actions change with
  the state.
- **Items** — add, reorder, complete. Each item references a
  catalog item and, optionally, an odontogram tooth treatment.
  Completing an item publishes
  `treatment_plan.treatment_completed` (with
  `treatment_category_key` for recalls).
- **Doctor per treatment.** Every item carries its own
  `assigned_professional_id`. New items inherit the plan's doctor.
  Click the coloured chip next to the item name to assign a
  different professional (e.g. filling by Dr A, endodontics by
  Dr B). When two or more doctors are involved in the plan, the
  chip colours make the mix visible at a glance. The chip stays
  editable while the item is pending, even after the plan is
  validated and the budget is active — reassignment is operational
  and does not change the patient-facing contract. Once an item is
  marked as completed, the chip becomes a read-only indicator and
  keeps showing `assigned_professional_id` (the clinician
  responsible for the treatment); completion can be triggered by
  reception or an admin on behalf of the clinician, so "who clicked
  Complete" is intentionally not the chart's reference.
- **Linked budget.** **Generate budget** / **Link to existing
  budget** / **Sync** buttons as needed. The plan publishes
  `treatment_plan.treatment_added / _removed /
  budget_sync_requested` so `budget` keeps the budget up to date.
- **Contacts** — front-desk touchpoint history. Useful when the
  plan is *pending* awaiting acceptance.
- **Clinical notes.** Can be attached to the plan from the
  `clinical_notes` module (slot `patient.detail.clinical.notes`).

## Confirm a plan

> Requires `treatment_plan.plans.confirm`.

1. On a `draft` plan, click **Confirm**.
2. `treatment_plan.confirmed` is published. The plan moves to
   `pending`.
3. If no budget was linked, **Generate budget** creates a new one
   on the `budget` module.

## Mark items as performed

> Requires `treatment_plan.plans.write`.

1. On the item, click **Mark as done**.
2. `treatment_plan.treatment_completed` is published. `recalls` can
   suggest a follow-up recall based on `treatment_category_key`.
3. To record a clinical note at that moment, use the *Add note*
   button (contributed by `clinical_notes`).

## Multi-session treatments

Some catalog items (e.g. crown, root canal) carry a **session
template** with a label and price per step. When the treatment is
added to a plan, one session is created per step.

- The item header shows an **X/Y sessions** progress chip.
- Below the item, the session list renders one row per session (✓
  icon when completed, dashed circle when pending).
- Click the check on a pending session to mark it done — publishes
  `treatment_plan.item_session_completed`; `payments` records an
  "earned" entry for that amount.
- The item is finalized automatically when the last pending session
  is completed (the legacy completion flow runs at that point).
- Cancel a session if it was not delivered — no earned entry is
  generated.
- If the treatment is marked performed from the **odontogram**, the
  full price is charged through that path and the item's pending
  sessions are cancelled automatically — the total is never charged
  twice.

## Change the plan's doctor

> Requires `treatment_plan.plans.write`.

1. Open **Edit plan** and pick a new professional.
2. If there are pending items still assigned to the previous
   doctor, a confirmation appears: *"Reassign pending treatments?"*.
3. Choose **Yes, reassign pending** to push all matching pending
   items onto the new doctor in the same save. Items with an
   explicit override (different doctor) and completed items are
   never touched.
4. Choose **No, keep as they are** to update only the plan-level
   doctor; the items stay where they were.

## Close or reactivate

> Closing requires `treatment_plan.plans.close`. Reactivating
> requires `treatment_plan.plans.reactivate`.

1. **Close** — pick reason: rejected, expired, cancelled,
   abandoned, or *other*. Publishes `treatment_plan.closed` with
   `closure_reason`.
2. **Reactivate** — back to `draft`. Publishes
   `treatment_plan.reactivated`. **Re-confirming** generates a fresh
   quote (the previously rejected/expired one becomes history and no
   longer locks the plan).
3. **Automatic reactivation** — a plan closed as *rejected by the
   patient* returns to *In progress* on its own if the patient accepts
   a new version of the quote (*Resend* button on the quote).

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View detail, items, and contacts | `treatment_plan.plans.read` |
| Add/reorder items, complete them, log contacts | `treatment_plan.plans.write` |
| Confirm (draft → pending) | `treatment_plan.plans.confirm` |
| Close | `treatment_plan.plans.close` |
| Reactivate | `treatment_plan.plans.reactivate` |

## Troubleshooting

- **Confirmed the plan but no budget appears.** Confirming
  auto-creates the draft budget; reload the page. If the plan already
  had a live draft, it is reused instead of creating another.
- **The plan shows as locked.** Only *sent* or *accepted* budgets lock
  (they are a contract with the patient). A cancelled, rejected or
  expired budget does not lock: you can keep editing the plan.
- **I cancelled the quote from the budgets module.** The linked
  *pending* plan returns to *draft* on its own so you can edit and
  re-confirm it.
- **Patient accepted the budget but the plan is still pending.**
  Check that `budget.accepted` is flowing (the `budget` module must
  be installed and the budget actually accepted). The
  `on_budget_accepted` handler moves it to *active*.
- **Cannot delete an item.** The item is already marked as done.
  Completed items remain as history.
- **Cannot complete an item.** Your role lacks
  `treatment_plan.plans.write`.
