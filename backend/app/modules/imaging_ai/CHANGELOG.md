# Changelog — imaging_ai

## Unreleased

- fix: pano can now complete a real run against `dental-pano-ai`. Upstream
  writes only `<output>/<stem>.csv` unless `--debug` is passed, and puts the
  overlays in `<output>/<stem>/`; the runner passed no `--debug` and scanned
  only the top level, so every real run reported "pano produced no images"
  and the findings CSV was dropped. It now passes `--debug`, reads artifacts
  recursively, and ingests the CSV as a draft (`text/plain`, `ai-findings`
  tag) alongside the overlays.
- fix: the pano checkout's model paths are resolved as `./models/...`
  relative to cwd, and the subprocess inherited the backend's cwd, so the
  load failed before inference; it now runs with the checkout as cwd.
- fix: the pano interpreter is operator-configurable via
  `DENTALPIN_PANO_PYTHON`, so a checkout can run on its own venv. Its
  `main.py` imports torch, detectron2 and ultralytics (AGPL) and pins
  `pillow==9.5.0`; the promise that those stay out of the backend image now
  holds instead of being documentation.
- fix: nnU-Net receives the weights dir as `nnUNet_results` (it resolves
  `-d 112` through that variable, so the existence-checked dir was
  previously dropped and the subprocess searched the backend's cwd), and
  asks for exactly the folds present under the weights dir. The public
  Zenodo zip ships `fold_0` only, while `nnUNetv2_predict` defaults to
  `-f 0 1 2 3 4` and aborted on `fold_1`.
- fix: the test double for pano now mimics upstream's real output layout
  and its cwd-relative model loading, so the round-1 failure mode (our tests
  green, every real run broken) is caught here.
- fix: a supervised agent session queues directly instead of proposing,
  since its tool call was already human-confirmed; an autonomous session
  still proposes.
- fix: the two meanings of the confirm button are now distinct labels
  ("Authorize run" vs "Mark reviewed"), making the §4 review step explicit
  (all 10 locales).
- fix: `list_dicom_documents` filters DICOM by mime/extension in SQL
  instead of loading every document of the patient and discarding rows in
  the router; `POST /ai-jobs/{id}/confirm` validates its response model like
  the other routes; `AiJob.document_id` is a real FK to `documents.id`
  (media was already a declared dependency, so no new `depends_on`).
- fix: draft lifecycle documented — confirmed drafts keep their `ai-draft`
  tag and title, and unconfirmed drafts stay in the patient's documents list
  until reviewed (intended for v1).
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
