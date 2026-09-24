---
module: imaging_viewer
screen: imaging
route: /imaging
related_endpoints:
  - GET /api/v1/imaging_viewer/patients/{patient_id}/studies
  - GET /api/v1/imaging_viewer/studies/{study_id}
  - GET /api/v1/imaging_viewer/studies/{study_id}/render
related_permissions:
  - imaging_viewer.studies.read
related_paths:
  - backend/app/modules/imaging_viewer/router.py
  - backend/app/modules/imaging_viewer/frontend/pages/imaging/index.vue
last_verified_commit: d8a9d663f37a1b806b6c985edca6195be4901404
screenshots: []
---

# Imaging

The imaging page lists a patient's viewable DICOM studies. Pick a
patient in the header (or open `/imaging?patient_id=...` from the
patient record); selecting a study shows its rendered image with
annotation overlays on top.

## Viewer

The image is rendered server-side (windowing applied) from the
clinic's own archive. If a study cannot be rendered, the page says so
instead of showing a broken image.

Studies shown here are a visualization aid only — never a diagnosis.
