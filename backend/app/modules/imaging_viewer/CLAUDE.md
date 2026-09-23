# imaging_viewer module

In-app DICOM study viewer. Indexes media documents holding DICOM bytes as
viewable studies and serves their frames to an embedded OHIF viewer (iframe).
Pixel data stays in the referenced media `Document`; this module owns the
study index row + the clinic-scoped frame proxy.

Viewer build: OHIF/Viewers `v3.12.14` (MIT — notice preserved in `NOTICE.md`).

## Public API

Routes mounted at `/api/v1/imaging_viewer/`.

- `GET    /patients/{id}/studies`        — list a patient's studies; `imaging_viewer.studies.read`
- `GET    /studies/{id}`                 — single study metadata; `imaging_viewer.studies.read`
- `POST   /patients/{id}/studies/index`  — index a media document as a study (201); `imaging_viewer.studies.write`
- `GET    /studies/{id}/frame`           — DICOM bytes for the viewer proxy; `imaging_viewer.studies.read`
- `GET    /dicomweb/studies`             — QIDO-RS minimal study list (JSON); `imaging_viewer.studies.read`
- `GET    /dicomweb/studies/{uid}/series/{s}/instances/{i}/frames/{n}` — WADO-RS minimal frame; `imaging_viewer.studies.read`
- `DELETE /studies/{id}`                 — soft-archive (204); `imaging_viewer.studies.write`
- `POST   /rvg/scan`                     — scan the clinic watch folder now; `imaging_viewer.rvg.read`
- `GET    /rvg/imports` (+`/{id}`)       — approval queue (filter `?status=`); `imaging_viewer.rvg.read`
- `POST   /rvg/imports/{id}/approve`     — materialize document + study, store link; `imaging_viewer.rvg.write`
- `POST   /rvg/imports/{id}/reject`      — keep row for audit; `imaging_viewer.rvg.write`
- `GET    /rvg/links`                    — approved DICOM-identity links; `imaging_viewer.rvg.read`
- `DELETE /rvg/links/{id}`               — drop a link (204); `imaging_viewer.rvg.write`
- `GET    /studies/{id}/annotations`     — overlay list; `imaging_viewer.studies.read`
- `POST   /studies/{id}/annotations`     — ruler/freehand/note (201, 422 on bad payload); `imaging_viewer.studies.write`
- `DELETE /annotations/{id}`             — archive overlay (204); `imaging_viewer.studies.write`

Cross-clinic ids resolve to 404 (`LookupError` in the service) — never an oracle.
Decided RVG rows answer 409 (`RvgConflictError`) on re-decide — never a 500.

## Data model

`ImagingStudy`: UUID PK, `clinic_id` (indexed FK), `patient_id` (indexed FK),
`document_id` (FK to `documents.id`), `study_uid`, `modality`, `study_date`,
`dicom_metadata` JSONB (extracted tags), `status` (`active`/`archived`).
Soft-delete only — patient data is never hard-deleted.

DICOM tag extraction (`service.extract_dicom_tags`) degrades gracefully: without
pydicom installed (or on malformed bytes) indexing still succeeds with the
caller-supplied `study_uid`/`modality` and empty tags.

RVG queue tables (`iv_0002`): `RvgLink` (unique clinic + DICOM PatientID →
patient, `created_by` attributes auto-imports) and `RvgImport` (unique clinic
+ content hash → file queue state: pending/approved/rejected/failed).
Matching scores national_id +60, DOB +25, name-token overlap up to +30;
threshold 40, ties stay suggestion-less. A 90s scheduler tick
(`get_scheduled_jobs` → `rvg_watch_tick`) scans
`<DENTALPIN_RVG_WATCH_DIR>/<clinic_id>/`; unset root is a silent no-op.
Design: `docs/technical/rvg-import-design.md`.

Annotation overlays (`iv_0003`, T2): `ImagingAnnotation` rows hold normalized
0-1 coordinates + optional server-computed mm (ruler + pixel spacing only —
never guessed). Originals immutable; study archive cascades; no new
permissions (read→`studies.read`, draw→`studies.write`). Display rules follow
`docs/technical/pano-overlay-design.md`. ROI statistics deferred: compressed
transfer syntaxes need native pixel codecs we don't ship.

## Dependencies

`manifest.depends = ["media", "patients"]`. Imports of `Document`,
`get_storage_backend`, and the `PHOTO_UPLOADED` event from `media` are legal
through the declared dependency. No other cross-module coupling.

## Permissions

- `imaging_viewer.studies.read` — list / view / frame proxy.
- `imaging_viewer.studies.write` — index / archive.
- `imaging_viewer.rvg.read` — scan trigger / approval queue / links.
- `imaging_viewer.rvg.write` — approve / reject / unlink (dentist + admin).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_imaging_studies` | READ | `ImagingStudyService.list_studies` | `imaging_viewer.studies.read` |
| `get_imaging_study` | READ | `ImagingStudyService.get_study` | `imaging_viewer.studies.read` |
| `index_imaging_study` | WRITE | `ImagingStudyService.index_study` | `imaging_viewer.studies.write` |
| `list_rvg_imports` | READ | `RvgService.list_imports` | `imaging_viewer.rvg.read` |
| `list_study_annotations` | READ | `AnnotationService.list` | `imaging_viewer.studies.read` |

## Events emitted / consumed

- Emits `imaging.study_indexed` on every index (study_id, clinic_id, patient_id,
  document_id, study_uid).
- Consumes `media.photo_uploaded` → auto-indexes DICOM-mime uploads (best-effort,
  never raises into the publisher).
- Consumes `patient.archived` → cascade soft-archive of the patient's studies,
  reject of their pending RVG suggestions, drop of their identity links.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Migrations on the `imaging_viewer` Alembic branch (`iv_0001`–`iv_0003`),
  depending on `media@med_0002` (the `documents` table must exist first).

## Gotchas

- **Frame proxy re-checks both rows** (study + document) against `clinic_id` —
  a study id alone is never trusted.
- **No PHI in frame URLs** beyond the opaque study id; study tokens (when the
  viewer needs them) are short-lived.
- **Viewer output is visualization, never diagnosis** (Slicer-license §4 posture).
- `pydicom` is a backend dependency of this module (`pyproject.toml`).

## CHANGELOG

See `./CHANGELOG.md`.
