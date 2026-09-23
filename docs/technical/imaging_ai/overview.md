---
module: imaging_ai
last_verified_commit: 0000000
---

# imaging_ai — technical overview

On-demand AI segmentation jobs over imaging studies (`nnUNetv2_predict`
subprocess behind the `Runner` protocol; torch/CUDA stay out of the backend).

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Auto-discovered facts about the `imaging_ai` module. See the module's
own notes at `backend/app/modules/imaging_ai/CLAUDE.md` for context
the scaffold could not infer.

## API surface

- `POST /api/v1/imaging_ai/patients/{patient_id}/ai-jobs`
- `GET /api/v1/imaging_ai/patients/{patient_id}/ai-jobs`
- `GET /api/v1/imaging_ai/ai-jobs/{job_id}`
- `DELETE /api/v1/imaging_ai/ai-jobs/{job_id}`

## Frontend

Page `/imaging-ai` (patient job list + statuses), gated by
`imaging_ai.jobs.read`.

## Permissions

`jobs.read`, `jobs.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** `imaging.ai_job_done`
- **Subscribes:** _(none — runs are queued manually)_

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/imaging_ai/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
