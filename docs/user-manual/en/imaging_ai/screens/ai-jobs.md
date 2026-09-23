---
module: imaging_ai
screen: ai-jobs
route: /imaging-ai
related_endpoints:
  - GET /api/v1/imaging_ai/patients/{patient_id}/ai-jobs
  - GET /api/v1/imaging_ai/ai-jobs/{job_id}
related_permissions:
  - imaging_ai.jobs.read
related_paths:
  - backend/app/modules/imaging_ai/router.py
  - backend/app/modules/imaging_ai/frontend/pages/imaging-ai/index.vue
last_verified_commit: 0000000
screenshots: []
---

# AI jobs

The AI jobs page lists a patient's segmentation runs with their status:
queued, running, done, failed, or cancelled.

## Opening the page

Open `/imaging-ai?patient_id=<uuid>` — for example from the patient record.
Without a patient selected, the page explains how to open it.

## Results

Finished runs link their overlay documents to the source study. AI output
is a visualization aid only — never a diagnosis.
