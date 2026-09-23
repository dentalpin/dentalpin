---
module: imaging_viewer
last_verified_commit: 0000000
---

# imaging_viewer — permissions

| Permission | Grants | Endpoints |
|---|---|---|
| `imaging_viewer.studies.read` | List studies, view metadata, frame proxy, DICOMweb façade, view overlays | `GET /patients/{id}/studies`, `GET /studies/{id}`, `GET /studies/{id}/frame`, `GET /dicomweb/studies`, `GET /dicomweb/studies/{uid}/…`, `GET /studies/{id}/annotations` |
| `imaging_viewer.studies.write` | Index a document as a study, archive a study, draw/archive overlays | `POST /patients/{id}/studies/index`, `DELETE /studies/{id}`, `POST /studies/{id}/annotations`, `DELETE /annotations/{id}` |
| `imaging_viewer.rvg.read` | Scan trigger, approval queue, identity links | `POST /rvg/scan`, `GET /rvg/imports*`, `GET /rvg/links` |
| `imaging_viewer.rvg.write` | Approve/reject imports, drop links | `POST /rvg/imports/{id}/approve`, `POST /rvg/imports/{id}/reject`, `DELETE /rvg/links/{id}` |

Role mapping (`manifest.role_permissions`): admin `*`; dentist read+write
(studies + rvg); hygienist/assistant/receptionist read-only.
