---
module: imaging_viewer
last_verified_commit: 0000000
---

# imaging_viewer — permissions

| Permission | Grants | Endpoints |
|---|---|---|
| `imaging_viewer.studies.read` | List studies, view metadata, PNG render, view overlays | `GET /patients/{id}/studies`, `GET /studies/{id}`, `GET /studies/{id}/render`, `GET /studies/{id}/annotations` |
| `imaging_viewer.studies.write` | Index a document as a study, archive a study, draw/archive overlays | `POST /patients/{id}/studies/index`, `DELETE /studies/{id}`, `POST /studies/{id}/annotations`, `DELETE /annotations/{id}` |
| `imaging_viewer.rvg.read` | Approval queue, identity links | `GET /rvg/imports*`, `GET /rvg/links` |
| `imaging_viewer.rvg.write` | Scan trigger, approve/reject imports, drop links | `POST /rvg/scan`, `POST /rvg/imports/{id}/approve`, `POST /rvg/imports/{id}/reject`, `DELETE /rvg/links/{id}` |

Role mapping (`manifest.role_permissions`): admin `*`; dentist read+write
(studies + rvg); hygienist/assistant/receptionist read-only.
