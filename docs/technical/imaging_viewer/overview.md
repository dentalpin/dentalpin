---
module: imaging_viewer
last_verified_commit: 0000000
---

# imaging_viewer — technical overview

In-app DICOM study viewer. Indexes media documents holding DICOM bytes as
viewable studies and renders them to PNG (server-side windowing) for the
viewer and the annotation canvas.

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Auto-discovered facts about the `imaging_viewer` module. See the module's
own notes at `backend/app/modules/imaging_viewer/CLAUDE.md` for context
the scaffold could not infer.

## API surface

- `GET /api/v1/imaging_viewer/patients/{patient_id}/studies`
- `GET /api/v1/imaging_viewer/studies/{study_id}`
- `POST /api/v1/imaging_viewer/patients/{patient_id}/studies/index`
- `GET /api/v1/imaging_viewer/studies/{study_id}/render`
- `DELETE /api/v1/imaging_viewer/studies/{study_id}`
- `POST /api/v1/imaging_viewer/rvg/scan` — scan the clinic watch folder now
- `GET /api/v1/imaging_viewer/rvg/imports` (+ `{id}`) — approval queue
- `POST /api/v1/imaging_viewer/rvg/imports/{id}/approve` — materialize + link
- `POST /api/v1/imaging_viewer/rvg/imports/{id}/reject`
- `GET /api/v1/imaging_viewer/rvg/links`, `DELETE /api/v1/imaging_viewer/rvg/links/{id}`
- `GET /api/v1/imaging_viewer/studies/{id}/annotations` — overlay list
- `POST /api/v1/imaging_viewer/studies/{id}/annotations` — draw (ruler/freehand/note)
- `DELETE /api/v1/imaging_viewer/annotations/{id}` — archive an overlay

## Frontend

Page `/imaging` (patient study list + embedded viewer + RVG import queue),
gated by `imaging_viewer.studies.read` (studies) and
`imaging_viewer.rvg.read` (queue; decisions need `rvg.write`).

## Permissions

`studies.read`, `studies.write`, `rvg.read`, `rvg.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** `imaging.study_indexed`
- **Subscribes:** `media.photo_uploaded`, `patient.archived`

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/imaging_viewer/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
