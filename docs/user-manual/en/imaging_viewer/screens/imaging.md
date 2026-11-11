---
module: imaging_viewer
screen: imaging
route: /imaging
related_endpoints:
  - GET /api/v1/imaging_viewer/patients/{patient_id}/studies
  - GET /api/v1/imaging_viewer/studies/{study_id}
  - GET /api/v1/imaging_viewer/studies/{study_id}/render
  - POST /api/v1/imaging_viewer/rvg/imports/approve-batch
related_permissions:
  - imaging_viewer.studies.read
  - imaging_viewer.rvg.write
related_paths:
  - backend/app/modules/imaging_viewer/router.py
  - backend/app/modules/imaging_viewer/frontend/pages/imaging/index.vue
last_verified_commit: f2f27de5779ae29cf903a88464d8e4bde4095a08
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
show their error. Pending rows carry checkboxes with a select-all
control, and two batch actions mirror the row buttons: approve the
selection via each row's suggestion, or approve the selection for the
patient currently picked in the header. The batch runs per row - an
already-decided row or a missing source file is reported by name while
the approved rows stand, and a summary toast states how many were
approved. Below the import
queue, linked sensor identities are listed with patient names and an
unlink action for correcting a wrong DICOM pairing.

## Viewer

The image is rendered server-side (windowing applied) from the
clinic's own archive. If a study cannot be rendered, the page says so
instead of showing a broken image.

Studies shown here are a visualization aid only — never a diagnosis.
