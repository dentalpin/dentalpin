---
module: imaging_ai
last_verified_commit: 0000000
---

# imaging_ai — technical overview

On-prem imaging AI: propose/confirm job lifecycle over patient DICOM,
scheduler execution, draft (never finalized) artifacts for clinician
review (compliance §4 posture).

Backends behind the `Runner` protocol (torch/CUDA stay out of the
backend image): `pano` by default (dental-pano-ai `main.py` wrap with
DICOM→PNG rendering — the path that runs end to end on single-frame
input; BYO checkout + weights, see `NOTICE.md` for the license
warning); `nnunet` for DICOM-series volumes stacked to NIfTI
(`DENTALPIN_NNUNET_WEIGHTS` + CUDA or explicit CPU opt-in).

Agent runs only propose; a clinician confirm authorizes execution and
fixes artifact attribution. The scheduler tick executes queued jobs
from every path and reaps stale runs.

## API surface

- `POST /api/v1/imaging_ai/patients/{patient_id}/ai-jobs`
- `POST /api/v1/imaging_ai/ai-jobs/{job_id}/confirm`
- `GET /api/v1/imaging_ai/patients/{patient_id}/ai-jobs`
- `GET /api/v1/imaging_ai/patients/{patient_id}/dicom-documents`
- `GET /api/v1/imaging_ai/ai-jobs/{job_id}`
- `DELETE /api/v1/imaging_ai/ai-jobs/{job_id}`

## Frontend

Page `/imaging-ai` (patient picker, DICOM series picker, backend
select, queue/confirm/cancel, draft overlays for review), gated by
`imaging_ai.jobs.read` (queue actions need `jobs.write`).

## Permissions

`jobs.read`, `jobs.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** `imaging.ai_job_done`, `imaging.ai_job_confirmed`
- **Subscribes:** _(none — runs are queued/proposed manually)_

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/imaging_ai/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
