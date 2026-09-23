# imaging_ai module

On-demand AI segmentation jobs over imaging studies. Queues a run, executes
it in a BackgroundTask on its own session (the request returns 202
immediately), and ingests result artifacts as media documents linked to the
source study.

Runner backends: `nnUNetv2_predict` subprocess v1 (torch/CUDA stay out of the
backend image); weights are operator-provided (Zenodo CC-BY-4.0 — see
`NOTICE.md`). Second backend `pano`: `dental-pano-ai` (MIT) `main.py` wrap
with DICOM→PNG rendering (single-frame panos); weights operator-provided
(S3 tarball, no stated terms). Third backend `ocr`: `tesseract` CLI sidecar
(Apache-2.0) producing `ocr.txt` transcripts ingested as paired text
artifacts (blank images succeed artifact-free). Unknown backends answer 422. A future
external worker implements the same `Runner` protocol without touching
callers.

## Public API

Routes mounted at `/api/v1/imaging_ai/`.

- `POST   /patients/{id}/ai-jobs` — queue a run (202); `imaging_ai.jobs.write`
- `GET    /patients/{id}/ai-jobs` — list a patient's jobs; `imaging_ai.jobs.read`
- `GET    /ai-jobs/{id}`          — single job; `imaging_ai.jobs.read`
- `DELETE /ai-jobs/{id}`          — cancel a queued job (204); `imaging_ai.jobs.write`

Cross-clinic ids resolve to 404 (`LookupError` in the service). Cancelling a
non-queued job answers 409 (mirrors the migration_import execute guard).

## Data model

`AiJob`: UUID PK, `clinic_id` (indexed), `patient_id` (indexed),
`study_id` + `document_id` as FK-free UUIDs (no dependency on the local-only
`imaging_viewer` branch — resolution is clinic-scoped at execution time),
`backend`, `model_id`/`model_version` (audit: which weights produced this),
`status` (`queued`/`running`/`done`/`failed`/`cancelled`), `queued_by`,
`log_excerpt`, `error`, `artifact_document_ids` JSONB. Job rows are never
hard-deleted.

## Dependencies

`manifest.depends = ["media", "patients"]`. Imports of `Document`,
`DocumentService`, `get_storage_backend`, and `Patient` are legal through the
declared dependencies. `study_id` intentionally has no FK (see above); a
post-merge follow-up adds it once `imaging_viewer` is on main.

## Permissions

- `imaging_ai.jobs.read` — list / view.
- `imaging_ai.jobs.write` — queue / cancel.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `queue_imaging_ai_job` | WRITE | `AiJobService.queue_job` | `imaging_ai.jobs.write` |
| `get_imaging_ai_job` | READ | `AiJobService.get_job` | `imaging_ai.jobs.read` |
| `list_imaging_ai_jobs` | READ | `AiJobService.list_jobs` | `imaging_ai.jobs.read` |

Queue-via-agent only queues; execution runs through the HTTP BackgroundTask
path (driving it inside the agent turn would block).

## Events emitted / consumed

- Emits `imaging.ai_job_done` on reaching a terminal state (job_id, clinic_id,
  patient_id, study_id, status).
- Consumes none (runs are queued manually — no auto-run on upload; GPU time
  is never spent implicitly).

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Migrations on the `imaging_ai` Alembic branch (`aij_0001`), depending on
  `media@med_0002` (artifacts land as media documents).

## Gotchas

- **Background execution opens its own session** (`async_session_maker`) —
  never the request's (migration_import pattern). Jobs always land terminal;
  failures are recorded on the row, never raised.
- **Runner never raises**: every failure mode encodes into
  `RunnerResult(ok=False, ...)`; missing binary/weights surface as clear job
  errors, not tracebacks.
- **Artifacts ingest through `DocumentService.create_document`** (kind `xray`,
  category `xray`, paired to the source document) so MIME validation,
  thumbnails, and clinic-scoped storage paths are honoured.
- **AI output is visualization aid, never diagnosis** (Slicer-license §4 posture).

## CHANGELOG

See `./CHANGELOG.md`.
