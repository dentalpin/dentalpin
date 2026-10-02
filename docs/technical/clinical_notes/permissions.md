---
module: clinical_notes
last_verified_commit: 2195ad0e
---

# Clinical Notes — permissions

Returned by `ClinicalNotesModule.get_permissions()` (relative names
— the registry namespaces them as `clinical_notes.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `clinical_notes.notes.read` | Listing clinical notes by owner, reading note counts, viewing attachments, reading recent patient notes, viewing notes grouped by plan, merged plan timelines, and fetching note templates. | `GET /notes`, `GET /notes/counts`, `GET /attachments`, `GET /patients/{patient_id}/recent`, `GET /patients/{patient_id}/by-plan`, `GET /treatment-plans/{plan_id}/merged`, `GET /note-templates`. |
| `clinical_notes.notes.write` | Creating polymorphic clinical notes (administrative, diagnosis, treatment, plan), updating existing notes, and deleting notes. | `POST /notes`, `PATCH /notes/{note_id}`, `DELETE /notes/{note_id}`. |

## Role assignment

Declared in the module manifest
([`backend/app/modules/clinical_notes/__init__.py`](../../../backend/app/modules/clinical_notes/__init__.py)):

| Role          | Permissions                  | Notes |
|---------------|------------------------------|-------|
| admin         | `*`                          | Full control over all clinical notes. |
| dentist       | `notes.read`, `notes.write`  | Read and write administrative, diagnosis, treatment, and plan notes. |
| hygienist     | `notes.read`, `notes.write`  | Read and record clinical notes for hygiene procedures and patient visits. |
| assistant     | `notes.read`, `notes.write`  | Read and record notes chairside or administrative notes. |
| receptionist  | `notes.read`, `notes.write`  | Read and record administrative notes and patient communication logs. |

See `backend/app/core/auth/permissions.py` for the canonical role
table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/clinical_notes/__init__.py`.
2. Add it to the role mapping in `manifest.role_permissions` (same
   file) so the appropriate roles can use it on a fresh install.
3. Wire the gate on the endpoint via
   `Depends(require_permission("clinical_notes.<name>"))`.
4. Mirror in `frontend/app/config/permissions.ts` under
   `PERMISSIONS.clinical_notes.*` so the UI can call
   `usePermissions().can(PERMISSIONS.clinical_notes.<name>)`.
5. Add a row to this file with the matching endpoints.
6. Re-run `python backend/scripts/generate_catalogs.py`.
