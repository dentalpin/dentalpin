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
last_verified_commit: 6502a0d9daf4538d57678e8c66fc422282389a04
screenshots: []
---

# Imaging

The imaging page lists a patient's viewable DICOM studies. Pick a
patient in the header (or open `/imaging?patient_id=...` from the
patient record); selecting a study shows its rendered image with
annotation overlays on top. While the patient resolves, the selector
shows a loading state; an unresolvable id reads "Unknown patient",
never a raw UUID. Study dates render in the clinic locale, and every
annotation delete button carries an accessible name. Triggering a manual
RVG watch-folder scan reports a summary toast (scanned / new /
auto-approved / failed counts). The RVG queue is
tabbed by status (pending / approved / rejected / failed) with live
counts on each tab; actions show only on pending rows and failed rows
show their error. Below the import
queue, linked sensor identities are listed with patient names and an
unlink action for correcting a wrong DICOM pairing.

## Viewer

The image is rendered server-side (windowing applied) from the
clinic's own archive. If a study cannot be rendered, the page says so
instead of showing a broken image.

Studies shown here are a visualization aid only — never a diagnosis.
