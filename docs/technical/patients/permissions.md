---
module: patients
last_verified_commit: 0e9a0ac
---

# Patients — permissions

Returned by `PatientsModule.get_permissions()` (relative names; the
permission registry namespaces them as `patients.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `patients.read` | Read patient identity rows (list, recent, detail, extended GET). | `GET /api/v1/patients`, `GET /api/v1/patients/recent`, `GET /api/v1/patients/{id}`, `GET /api/v1/patients/{id}/extended` |
| `patients.write` | Create, update, archive, edit extended demographics. | `POST /api/v1/patients`, `PUT /api/v1/patients/{id}`, `DELETE /api/v1/patients/{id}`, `PUT /api/v1/patients/{id}/extended`, `POST /api/v1/patients/import.csv`, `POST /api/v1/patients/{id}/restore` |

## Role assignment

Default role mappings (in `backend/app/core/auth/permissions.py`):

| Role | Patients access |
|------|-----------------|
| `admin` | Both (via `*`). |
| `dentist` | Both (via `clinical.*`). |
| `hygienist` | Read only (`clinical.patients.read`). |
| `assistant` | Both (`clinical.patients.*`). |
| `receptionist` | Both (`clinical.patients.*`). |

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/patients/__init__.py`.
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
