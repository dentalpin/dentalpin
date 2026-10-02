---
module: patient_timeline
last_verified_commit: 2195ad0e
---

# Patient Timeline — permissions

Returned by `PatientTimelineModule.get_permissions()` (relative names
— the registry namespaces them as `patient_timeline.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `patient_timeline.read` | Viewing the paginated chronological activity feed and event history for a patient, optionally filtered by event category. | `GET /patients/{patient_id}`. |

## Role assignment

Declared in the module manifest
([`backend/app/modules/patient_timeline/__init__.py`](../../../backend/app/modules/patient_timeline/__init__.py)):

| Role          | Permissions    | Notes |
|---------------|----------------|-------|
| admin         | `*`            | Full access to all patient timelines. |
| dentist       | `read`         | View patient activity history during diagnosis and treatment planning. |
| hygienist     | `read`         | View patient event timeline for appointment and clinical context. |
| assistant     | `read`         | View patient timeline for chairside and front-desk coordination. |
| receptionist  | `read`         | View patient history for scheduling and communication tracking. |

See `backend/app/core/auth/permissions.py` for the canonical role
table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/patient_timeline/__init__.py`.
2. Add it to the role mapping in `manifest.role_permissions` (same
   file) so the appropriate roles can use it on a fresh install.
3. Wire the gate on the endpoint via
   `Depends(require_permission("patient_timeline.<name>"))`.
4. Mirror in `frontend/app/config/permissions.ts` under
   `PERMISSIONS.patient_timeline.*` so the UI can call
   `usePermissions().can(PERMISSIONS.patient_timeline.<name>)`.
5. Add a row to this file with the matching endpoints.
6. Re-run `python backend/scripts/generate_catalogs.py`.
