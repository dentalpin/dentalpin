---
module: treatment_plan
last_verified_commit: 2195ad0e
---

# Treatment Plan — permissions

Returned by `TreatmentPlanModule.get_permissions()` (relative names
— the registry namespaces them as `treatment_plan.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `treatment_plan.plans.read` | Listing the treatment plan pipeline, searching plans, reading plan details, and viewing patient treatment plans. | `GET /treatment-plans/pipeline`, `GET /treatment-plans`, `GET /treatment-plans/patient/{patient_id}`, `GET /treatment-plans/{plan_id}`. |
| `treatment_plan.plans.write` | Creating and updating plans, modifying plan status, logging patient contact, deleting draft plans, managing planned items and multi-session steps, and linking/syncing/generating budgets. | `POST /treatment-plans`, `PUT /treatment-plans/{plan_id}`, `PATCH /treatment-plans/{plan_id}/status`, `POST /treatment-plans/{plan_id}/reopen`, `POST /treatment-plans/{plan_id}/contact-log`, `DELETE /treatment-plans/{plan_id}`, `POST /treatment-plans/{plan_id}/items`, `PUT /treatment-plans/{plan_id}/items/{item_id}`, `DELETE /treatment-plans/{plan_id}/items/{item_id}`, `PATCH /treatment-plans/{plan_id}/items/reorder`, `PATCH /treatment-plans/{plan_id}/items/{item_id}/complete`, `PATCH /treatment-plans/{plan_id}/items/{item_id}/sessions/{session_id}/complete`, `PATCH /treatment-plans/{plan_id}/items/{item_id}/sessions/{session_id}/cancel`, `PUT /treatment-plans/{plan_id}/items/{item_id}/sessions/{session_id}`, `POST /treatment-plans/{plan_id}/items/{item_id}/sessions`, `DELETE /treatment-plans/{plan_id}/items/{item_id}/sessions/{session_id}`, `POST /treatment-plans/{plan_id}/link-budget`, `POST /treatment-plans/{plan_id}/sync-budget`, `POST /treatment-plans/{plan_id}/generate-budget`. |
| `treatment_plan.plans.confirm` | Confirming an accepted treatment plan with patient consent. | `POST /treatment-plans/{plan_id}/confirm`. |
| `treatment_plan.plans.close` | Closing a completed, rejected, or abandoned treatment plan. | `POST /treatment-plans/{plan_id}/close`. |
| `treatment_plan.plans.reactivate` | Reactivating a previously closed or archived treatment plan. | `POST /treatment-plans/{plan_id}/reactivate`. |

## Role assignment

Declared in the module manifest
([`backend/app/modules/treatment_plan/__init__.py`](../../../backend/app/modules/treatment_plan/__init__.py)):

| Role          | Permissions                                                                    | Notes |
|---------------|--------------------------------------------------------------------------------|-------|
| admin         | `*`                                                                            | Full control across all treatment plan workflows. |
| dentist       | `*`                                                                            | Full clinical control to create, confirm, and manage treatment plans. |
| hygienist     | `plans.read`                                                                   | View treatment plans for clinical reference. |
| assistant     | `plans.read`, `plans.write`                                                    | View and update plans, items, and sessions chairside. |
| receptionist  | `plans.read`, `plans.write`, `plans.close`, `plans.reactivate`                 | Drives the pipeline inbox, records contact logs, closes or reactivates returning patient plans; confirmation stays with doctors. |

See `backend/app/core/auth/permissions.py` for the canonical role
table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/treatment_plan/__init__.py`.
2. Add it to the role mapping in `manifest.role_permissions` (same
   file) so the appropriate roles can use it on a fresh install.
3. Wire the gate on the endpoint via
   `Depends(require_permission("treatment_plan.<name>"))`.
4. Mirror in `frontend/app/config/permissions.ts` under
   `PERMISSIONS.treatment_plan.*` so the UI can call
   `usePermissions().can(PERMISSIONS.treatment_plan.<name>)`.
5. Add a row to this file with the matching endpoints.
6. Re-run `python backend/scripts/generate_catalogs.py`.
