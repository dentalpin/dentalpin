---
module: imaging_ai
last_verified_commit: 0000000
---

# imaging_ai — permissions

| Permission | Grants | Endpoints |
|---|---|---|
| `imaging_ai.jobs.read` | List jobs, view status/artifacts | `GET /patients/{id}/ai-jobs`, `GET /ai-jobs/{id}` |
| `imaging_ai.jobs.write` | Queue a run, cancel a queued job | `POST /patients/{id}/ai-jobs`, `DELETE /ai-jobs/{id}` |

Role mapping (`manifest.role_permissions`): admin `*`; dentist read+write;
hygienist/assistant/receptionist read-only.
