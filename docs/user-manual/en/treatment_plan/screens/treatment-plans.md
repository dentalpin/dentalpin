---
module: treatment_plan
screen: list
route: /treatment-plans
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
  - backend/app/modules/treatment_plan/frontend/pages/treatment-plans/index.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: b1b82f5
---

# Plans inbox

Inbox of the clinic's treatment plans. Organized into **five tabs**
aligned with the plan state machine, plus a pipeline view that
surfaces the follow-up queue.

## At a glance

- **Tabs by state.** *Drafts* (not confirmed), *Pending* (waiting
  for patient acceptance), *Active* (treatment in progress),
  *Completed*, *Closed* (rejected, expired, cancelled, abandoned,
  or *other*).
- **Pipeline.** Aggregate inbox view (`GET /pipeline`) with totals
  per column and plans that need front-desk action (pending with no
  recent contact, unsent budget, etc.).
- **Search and filters.** Search by patient, title or plan number; filter
  by assigned professional, creation date, and closure reason.
- **Budget sync.** Each plan has a linked budget (or creates one on
  confirm). Plan changes propagate to the budget via snapshot
  events — no need to edit the budget by hand.
- **Clinical notes.** Since issue #60, notes are not stored on the
  plan: they are delegated to the `clinical_notes` module. The plan
  only logs executions.

## Find a plan

1. Switch tabs or enter the pipeline.
2. Filter by professional, date, or closure reason as needed.
3. Click a row to open the [detail](./treatment-plans_id.md).

## Create a plan

> Requires `treatment_plan.plans.write`.

1. Click **New plan** (top right) → goes to `/treatment-plans/new`.
2. Pick patient, professional, and add treatments.

## Log a contact

> Requires `treatment_plan.plans.write`.

1. On the row or detail, use **Log contact** to record a phone /
   WhatsApp / email touchpoint by the front desk.
2. These contacts feed the pipeline view so plans don't go too long
   without activity.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View inbox, pipeline, and detail | `treatment_plan.plans.read` |
| Create, edit, add items, log contacts | `treatment_plan.plans.write` |
| Confirm (draft → pending) | `treatment_plan.plans.confirm` |
| Close a plan | `treatment_plan.plans.close` |
| Reactivate a closed plan | `treatment_plan.plans.reactivate` |

## Troubleshooting

- **Plan is pending but the patient accepted.** The `budget.accepted`
  event moves it to *active* automatically. If it hasn't, check
  that the budget is actually accepted and both modules are
  installed.
- **Closed plan is missing.** On the *Closed* tab, filter by
  *closure reason*. The default includes all.
- **No *Confirm* button.** Your role lacks
  `treatment_plan.plans.confirm` or the plan is already in pending
  or later.
