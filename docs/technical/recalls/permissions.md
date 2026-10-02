---
module: recalls
last_verified_commit: 2195ad0e
---

# Recalls — permissions

Returned by `RecallsModule.get_permissions()` (relative names
— the registry namespaces them as `recalls.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `recalls.read` | Listing and filtering monthly recalls, viewing dashboard statistics, fetching next-recall suggestions, reading recall settings, exporting recalls to CSV, viewing patient recalls, viewing recall details, and reading contact attempt logs. | `GET /`, `GET /stats/dashboard`, `GET /suggestions/next`, `GET /settings`, `GET /export.csv`, `GET /patients/{patient_id}`, `GET /{recall_id}`, `GET /{recall_id}/attempts`. |
| `recalls.write` | Creating recalls, updating recall settings, patching recall details, snoozing recalls, cancelling recalls, marking recalls done, logging contact attempts, and linking appointments to recalls. | `POST /`, `PUT /settings`, `PATCH /{recall_id}`, `POST /{recall_id}/snooze`, `POST /{recall_id}/cancel`, `POST /{recall_id}/done`, `POST /{recall_id}/attempts`, `POST /{recall_id}/link-appointment`. |
| `recalls.delete` | Hard deleting a recall record. | `DELETE /{recall_id}`. |

## Role assignment

Declared in the module manifest
([`backend/app/modules/recalls/__init__.py`](../../../backend/app/modules/recalls/__init__.py)):

| Role          | Permissions    | Notes |
|---------------|----------------|-------|
| admin         | `*`            | Full control over recalls including hard deletion. |
| dentist       | `read`, `write`| Create recall recommendations, update recall records, log contact attempts. |
| hygienist     | `read`, `write`| Create recall recommendations, update recall records, log contact attempts. |
| assistant     | `read`, `write`| Create recall recommendations, update recall records, log contact attempts. |
| receptionist  | `read`, `write`| Manage monthly call list, log patient contact attempts, schedule/snooze/complete recalls. |

See `backend/app/core/auth/permissions.py` for the canonical role
table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/recalls/__init__.py`.
2. Add it to the role mapping in `manifest.role_permissions` (same
   file) so the appropriate roles can use it on a fresh install.
3. Wire the gate on the endpoint via
   `Depends(require_permission("recalls.<name>"))`.
4. Mirror in `frontend/app/config/permissions.ts` under
   `PERMISSIONS.recalls.*` so the UI can call
   `usePermissions().can(PERMISSIONS.recalls.<name>)`.
5. Add a row to this file with the matching endpoints.
6. Re-run `python backend/scripts/generate_catalogs.py`.
