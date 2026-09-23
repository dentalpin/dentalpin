---
module: imaging_viewer
screen: imaging
route: /imaging
related_endpoints:
  - GET /api/v1/imaging_viewer/patients/{patient_id}/studies
  - GET /api/v1/imaging_viewer/studies/{study_id}
  - GET /api/v1/imaging_viewer/studies/{study_id}/frame
related_permissions:
  - imaging_viewer.studies.read
related_paths:
  - backend/app/modules/imaging_viewer/router.py
  - backend/app/modules/imaging_viewer/frontend/pages/imaging/index.vue
last_verified_commit: 0000000
screenshots: []
---

# Imaging

The imaging page lists a patient's viewable DICOM studies. Selecting a
study opens it in the embedded viewer.

## Opening the page

Open `/imaging?patient_id=<uuid>` — for example from the patient record.
Without a patient selected, the page explains how to open it.

## Viewer

The viewer renders the study from the clinic's own archive. If the
interactive viewer cannot load, the page offers the original DICOM file
for download instead.

Studies shown here are a visualization aid only — never a diagnosis.
