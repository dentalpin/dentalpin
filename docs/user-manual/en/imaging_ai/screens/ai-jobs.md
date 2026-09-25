---
module: imaging_ai
screen: ai-jobs
route: /imaging-ai
related_endpoints:
  - POST /api/v1/imaging_ai/patients/{patient_id}/ai-jobs
  - POST /api/v1/imaging_ai/ai-jobs/{job_id}/confirm
  - GET /api/v1/imaging_ai/patients/{patient_id}/ai-jobs
  - GET /api/v1/imaging_ai/patients/{patient_id}/dicom-documents
  - GET /api/v1/imaging_ai/ai-jobs/{job_id}
  - DELETE /api/v1/imaging_ai/ai-jobs/{job_id}
related_permissions:
  - imaging_ai.jobs.read
  - imaging_ai.jobs.write
related_paths:
  - backend/app/modules/imaging_ai/router.py
  - backend/app/modules/imaging_ai/frontend/pages/imaging-ai/index.vue
last_verified_commit: ad339611ade2847809b6478a60a7a1354990b432
screenshots: []
---

# AI jobs

The AI jobs page runs the full flow a dentist follows: pick a patient,
pick the DICOM files (first checked is the primary document; check the
rest of the series for volumetric nnU-Net runs), choose the backend
(pano for single frames, nnU-Net for series volumes), and queue the run.
Jobs list with their status — proposed, queued, running, done, failed,
cancelled — plus errors and the runner log tail.

## Opening the page

Open `/imaging-ai` and search the patient, or deep-link
`/imaging-ai?patient_id=<uuid>` from the patient record. Without patient
read rights, only the deep link works.

## Drafts and review

Finished runs ingest their overlays as AI draft documents — never gallery
radiographs, never paired to the source. Review the draft overlay, then
Confirm: proposed runs start executing, finished drafts are marked
reviewed. Nothing the model produces enters the clinical record without
that explicit step. AI output is a visualization aid only — never a
diagnosis.
