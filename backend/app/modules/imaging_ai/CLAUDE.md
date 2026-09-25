# imaging_ai module

On-prem imaging AI: propose/confirm job lifecycle over patient DICOM,
scheduler execution, draft (never finalized) artifacts for clinician
review. Default backend `pano` (single-frame, works end to end);
`nnunet` takes a DICOM-series volume plus operator weights.

## Public API

Routes mounted at `/api/v1/imaging_ai/`.

- `POST   /patients/{id}/ai-jobs` — queue (attributed) or propose (agent) a run (202); `imaging_ai.jobs.write`
- `POST   /ai-jobs/{id}/confirm` — confirm: proposed→queued (stamps confirmer) or done→reviewed; else 409; `imaging_ai.jobs.write`
- `GET    /patients/{id}/ai-jobs` — list a patient's jobs; `imaging_ai.jobs.read`
- `GET    /patients/{id}/dicom-documents` — DICOM candidates for the series picker; `imaging_ai.jobs.read`
- `GET    /ai-jobs/{id}`          — single job; `imaging_ai.jobs.read`
- `DELETE /ai-jobs/{id}`          — cancel a proposed/queued job (204); `imaging_ai.jobs.write`

Cross-clinic ids resolve to 404 (`LookupError` in the service).
Unknown backends answer 422; nnU-Net without a series answers 422.

## Data model

`AiJob`: UUID PK, `clinic_id` (indexed), `patient_id` (indexed),
`document_id` (FK-free UUID) + `series_document_ids` JSONB for
volumetric backends, `backend` (default `pano`), `model_id`/
`model_version` (audit), `status` (`proposed`/`queued`/`running`/
`done`/`failed`/`cancelled`), `queued_by` (null only while proposed),
`review_status` (`pending_review`/`confirmed`) + `confirmed_by/at`,
`log_excerpt`, `error`, `artifact_document_ids` JSONB. Job rows are
never hard-deleted.

## Dependencies

`manifest.depends = ["media", "patients"]`. Imports of `Document`,
`DocumentService`, `get_storage_backend`, and `Patient` are legal
through the declared dependencies. No dependency on `imaging_viewer`
(the series picker reads media documents, deep links carry
`patient_id`).

## Permissions

- `imaging_ai.jobs.read` — list / view / series picker.
- `imaging_ai.jobs.write` — queue / propose / confirm / cancel.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `queue_imaging_ai_job` | WRITE | `AiJobService.queue_job` (proposes: `queued_by=None`) | `imaging_ai.jobs.write` |
| `confirm_imaging_ai_job` | WRITE | `AiJobService.confirm_job` (supervisor stamps) | `imaging_ai.jobs.write` |
| `get_imaging_ai_job` | READ | `AiJobService.get_job` | `imaging_ai.jobs.read` |
| `list_imaging_ai_jobs` | READ | `AiJobService.list_jobs` | `imaging_ai.jobs.read` |

Confirm needs a supervised session (`ctx.supervisor_id`); autonomous
agents get an explicit error, never silent attribution.

## Events emitted / consumed

- Emits `imaging.ai_job_done` on reaching a terminal state (job_id, clinic_id, patient_id, status).
- Emits `imaging.ai_job_confirmed` when a clinician confirms drafts (job_id, clinic_id, patient_id, confirmed_by).
- Consumes none (runs are queued/proposed manually — no auto-run on upload; GPU time is never spent implicitly).

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Migrations on the `imaging_ai` Alembic branch (`aij_0001`), depending on
  `media@med_0002` (artifacts land as media documents).
- Scheduled jobs (only while installed): `imaging_ai_queue` every 60 s
  (claim + execute, row-locked), `imaging_ai_stuck_reaper` every 5 min
  (fail `running` older than 2 h).

## Gotchas

- **Background execution opens its own session** (`async_session_maker`) — never the request's. Jobs always land terminal; failures are recorded on the row, never raised.
- **Runner never raises**: every failure mode encodes into `RunnerResult(ok=False, ...)`; missing binary/weights/CUDA surface as clear job errors, not tracebacks.
- **Artifacts are drafts** (compliance §4): kind `document` keeps them out of the photo/xray gallery rail and fires no photo event; source linkage lives in `artifact_document_ids` — media pairing is never written. Confirm records the review on the job; it never rewrites media rows.
- **nnU-Net needs a volume**: queue validates ≥2 slices of one series; execution stacks to `<case>_0000.nii.gz` via `volume.py` (identity orientation — sanity-check overlays on first use). Single frames belong to pano.
- **CLI contracts are pinned**: `build_nnunet_cmd` / `build_pano_cmd` are pure argv builders with tests — assert the command line, not just the exit code. The test doubles mimic UPSTREAM's layout, not ours: the round-1 lesson was a stub that wrote an overlay at the top level while the real CLI writes a CSV there and the images in a subdirectory.
- **Never trust a weight dir you only existence-checked**: nnU-Net finds its model through the `nnUNet_results` env var (`nnunet_child_env`), not through a flag, and it defaults to folds 0-4, so `available_folds()` asks for what the operator actually downloaded.
- **The pano checkout runs on its own interpreter** (`DENTALPIN_PANO_PYTHON`) with `cwd=app_dir`; its torch/detectron2/ultralytics deps never enter the backend image.
- **Drafts are drafts until reviewed** (§4): confirmed drafts keep their `ai-draft` tag and title, and unconfirmed drafts stay listed in the patient's documents indefinitely — that is the intended v1 lifecycle, not a leak.
- **AI output is visualization aid, never diagnosis** (compliance §4 posture).

## CHANGELOG

See `./CHANGELOG.md`.
