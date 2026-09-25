---
module: imaging_ai
last_verified_commit: ad339611ade2847809b6478a60a7a1354990b432
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

Both backends shell out to operator-provided tooling, so both take their
whole environment from configuration rather than from the backend image:

| Var | Backend | Meaning |
|---|---|---|
| `DENTALPIN_PANO_APP` | pano | Path to the `dental-pano-ai` checkout (its `main.py` must exist there) |
| `DENTALPIN_PANO_PYTHON` | pano | Interpreter for that checkout's venv. Its deps (torch, detectron2, ultralytics AGPL) never enter the backend image; unset means the backend's own python |
| `DENTALPIN_NNUNET_WEIGHTS` | nnunet | Results root containing `Dataset112_*`; passed to the subprocess as `nnUNet_results`, which is how nnU-Net resolves `-d 112` |
| `DENTALPIN_NNUNET_ALLOW_CPU` | nnunet | `1` opts into CPU-only (slow) execution |

The pano runner executes upstream with the checkout as its working
directory (upstream resolves `./models/...` relative to cwd) and reads
upstream's real output layout: the per-FDI findings CSV plus, with
`--debug`, the overlays in `<output>/<stem>/`. The nnU-Net runner asks
for exactly the folds present under the weights dir, because
`nnUNetv2_predict` otherwise defaults to `-f 0 1 2 3 4` and aborts on the
first fold the operator never downloaded (the public Zenodo zip ships
`fold_0` only).

Agent runs only propose unless the session is supervised: an autonomous
session creates a `proposed` job that a clinician confirms, while a
supervised session (the tool call was already human-confirmed) queues
directly, stamped with the supervisor. Either way the scheduler executes
queued jobs and reaps stale runs.

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
