---
module: migration_import
last_verified_commit: 2195ad0e
---

# migration_import — permissions

All permissions are namespaced under `migration_import.`.

| Permission                      | Endpoints                                              | Default roles |
|---------------------------------|--------------------------------------------------------|---------------|
| `migration_import.job.read`     | `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/warnings`, `POST /jobs/{id}/preview`, `GET /jobs/{job_id}/proposals` | admin (`*`) |
| `migration_import.job.write`    | `POST /jobs`, `POST /jobs/{id}/validate`               | admin (`*`)   |
| `migration_import.job.execute`  | `POST /jobs/{id}/execute`, `POST /jobs/{job_id}/proposals`, `PATCH /jobs/{job_id}/proposals/{canonical_uuid}`, `POST /jobs/{job_id}/proposals/bulk_accept` | admin (`*`)   |
| `migration_import.binary.write` | `POST /jobs/{id}/binaries` (sync agent)                | admin (`*`)   |

`manifest.role_permissions` grants `*` to `admin` only. No other role
sees the page or can execute. Widen at the manifest level if a tenant
wants a dedicated migration operator role.

The sync agent should be issued an account with the admin role (or a
narrower role that only holds `migration_import.binary.write`) and
ideally tied to a service-account user.
