---
module: imaging_ai
last_verified_commit: 0000000
---

# imaging_ai — permissions

| Permission | Grants | Endpoints |
|---|---|---|
| `imaging_ai.jobs.read` | List jobs, view status/artifacts, series picker | `GET /patients/{id}/ai-jobs`, `GET /ai-jobs/{id}`, `GET /patients/{id}/dicom-documents` |
| `imaging_ai.jobs.write` | Queue/propose a run, confirm, cancel | `POST /patients/{id}/ai-jobs`, `POST /ai-jobs/{id}/confirm`, `DELETE /ai-jobs/{id}` |

Role mapping (`manifest.role_permissions`): admin `*`; dentist read+write;
hygienist/assistant/receptionist read-only.
