# Changelog — imaging_ai

## Unreleased

- feat: propose/confirm lifecycle (review #504): agent proposals execute
  only after a clinician confirm stamps `queued_by`; scheduler tick
  (`imaging_ai_queue` every 60 s, row-locked claim) executes queued jobs
  from every path; stuck `running` jobs fail after 2 h. HTTP route no
  longer dispatches its own BackgroundTask.
- feat: default backend is now `pano` (the path that runs end to end on
  single-frame input); `nnunet` reads `DENTALPIN_NNUNET_WEIGHTS` +
  `DENTALPIN_NNUNET_ALLOW_CPU`, refuses without weights/CUDA, takes a
  DICOM series (≥2 slices) stacked to `<case>_0000.nii.gz` via the new
  `volume.py`, and both CLI contracts are pinned by argv tests.
- feat: artifacts are drafts (compliance §4): kind `document` (never
  gallery `xray`), no media pairing written, source linkage on the job
  row only; `POST /ai-jobs/{id}/confirm` records the clinician review
  (`imaging.ai_job_confirmed`); page shows draft overlays + Confirm.
- feat: runnable UI — patient picker (search or `?patient_id` deep link),
  DICOM series picker (`GET /patients/{id}/dicom-documents`), backend
  select, queue/confirm/cancel from the page; screen docs en+es.
- fix: `study_id` dropped (opaque, unvalidated); OCR backend extracted
  (follow-up module, next to expenses); pano weights ship BYO with a
  license warning (S3 tarball has no stated terms — confirm before
  production use).
- fix: `noPatientHint` drops the `<uuid>` placeholder (vue-i18n build
  rejects HTML-like messages).
