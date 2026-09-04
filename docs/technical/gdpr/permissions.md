---
module: gdpr
last_verified_commit: 8b8e9375
---

# gdpr — permissions

Returned by `GdprModule.get_permissions()`
(relative names; the registry namespaces them as `gdpr.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `gdpr.requests.read` | List and view data-subject requests, erasure audit, exports | `GET /api/v1/gdpr/requests`, `GET /api/v1/gdpr/requests/{id}`, `GET /api/v1/gdpr/export/{patient_id}` |
| `gdpr.requests.write` | Create/transition DSRs (never delete — accountability, Art. 5(2)); run erasure | `POST /api/v1/gdpr/requests`, `PATCH /api/v1/gdpr/requests/{id}`, `POST /api/v1/gdpr/erasure` |
| `gdpr.consents.read` | List patient consents | `GET /api/v1/gdpr/consents` |
| `gdpr.consents.write` | Record consent grant or withdrawal | `POST /api/v1/gdpr/consents` |
| `gdpr.retention.read` | List active retention policies | `GET /api/v1/gdpr/retention` |
| `gdpr.retention.write` | Create/update/delete retention policies | `POST /api/v1/gdpr/retention`, `PATCH /api/v1/gdpr/retention/{id}`, `DELETE /api/v1/gdpr/retention/{id}` |
| `gdpr.audit.read` | View the erasure audit log | `GET /api/v1/gdpr/audit` |
| `gdpr.breaches.read` | List and view data-breach reports | `GET /api/v1/gdpr/breaches`, `GET /api/v1/gdpr/breaches/{id}` |
| `gdpr.breaches.write` | Create and update data-breach reports | `POST /api/v1/gdpr/breaches`, `PATCH /api/v1/gdpr/breaches/{id}` |

## Role assignment

admin gets wildcard (`*`); dentist reads requests/consents/audit/retention;
hygienist reads requests only; assistant reads requests + consents;
receptionist reads+writes requests and consents and reads breaches
(front-desk answers most DSRs day-to-day).

See `backend/app/modules/gdpr/__init__.py` for the canonical role table
(`manifest.role_permissions`).

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/gdpr/__init__.py`.
2. Grant it to roles in `manifest.role_permissions`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.