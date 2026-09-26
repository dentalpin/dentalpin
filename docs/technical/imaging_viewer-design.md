# imaging_viewer — local design record (B1a OHIF embed)

> Local-only (branch `pr/imaging-viewer-local`, unpushed). Design-first record for
> the OHIF/Viewers integration. No tracker post, no PR — codes only here until a
> pipeline slot opens and the maintainer signs the design.
> License basis: `docs/technical/external-repos-reference.md` §B1a
> (OHIF MIT @ `v3.12.14`, attribution preserved).

## Goal

View a patient's DICOM studies (incl. CBCT) inside DentalPin, read-only,
with the same clinic isolation and RBAC as everything else. Today's state is
preview-only JPEGs (`media` module); CBCT is metadata-only (`todos.md:255`).

## Non-goals (MVP)

- No annotation/measurement persistence (no write path into PACS semantics).
- No AI segmentation in this module (B1b sidecar is the follow-up; this module
  only reserves the "AI job" hook point).
- No Orthanc/dcm4chee sidecar in MVP — built-in proxy unless the spike proves
  multi-frame CBCT can't be served that way.
- No copying of unlicensed/GPL/NC code (reference file §B1a/B1b tables govern).

## Module shape (per `docs/checklists/new-module.md`)

- Name `imaging_viewer`, `category: official`, `version 0.1.0`, `license BSL-1.1`.
- `manifest.depends = ["media", "patients"]` — studies are indexed off media
  documents; patient linkage via patients. No other cross-module access.
- `installable: True`, `auto_install: False` (optional module default),
  `removable: True` (+ round-trip uninstall test).
- `role_permissions`: admin `*`; dentist `studies.read`; hygienist/assistant/
  receptionist mirror the `media` read pattern (dentist full, others read-only;
  finalized at build).
- `get_permissions()` returns `["studies.read"]` (MVP; `studies.write` reserved
  for the annotations follow-up and NOT shipped).

## Backend

- `models.py`: `ImagingStudy` — UUID PK, `clinic_id` FK indexed, `patient_id`,
  `document_id` (media FK, `depends`-legal), `study_uid`, `modality`,
  `dicom_metadata` JSONB, `status` (soft-delete for patient data), TIMESTAMPTZ.
- `service.py`: every query filters `clinic_id` (L1); pydicom metadata extraction
  (Study Date, Modality, Body Part — `todos.md:260-266`); JPEG preview reuses
  `media` derivatives, never duplicated.
- `router.py` (mounted `/api/v1/imaging_viewer/`, `ApiResponse` wrappers):
  - `GET /patients/{id}/studies` — `imaging_viewer.studies.read`, paginated
  - `GET /studies/{id}` — metadata
  - `GET /studies/{id}/frame?instance=&frame=` — DICOM frame bytes for the
    embedded viewer (JWT-gated, `clinic_id`-scoped, no PHI in URLs)
- `migrations/versions/iv_0001_initial.py` with `branch_labels = ("imaging_viewer",)`;
  register in `backend/alembic.ini` `version_locations` (M1) + `pyproject.toml`
  entry-point (entry-point parity test).
- Events (`EventType` additions): subscribe `media.photo_uploaded` → index DICOM;
  publish `imaging.study_indexed`. No direct service imports outside `depends`.

## Frontend (module layer `frontend/`)

- Pages: patient imaging list → study viewer (OHIF iframe + postMessage,
  pinned build `v3.12.14`, served from our static/vendor path, MIT notice kept).
- Gating via `PERMISSIONS.imaging_viewer.studies.read` + `usePermissions()`;
  Spanish-first strings, en/es parity; nav entry with namespaced permission.
- Auth passthrough: short-lived study token, viewer inherits session; RTL shell
  must not break the iframe (verified in spike).

## PHI / security

- Frame proxy never logs UIDs; study tokens TTL minutes; access audited.
- Slicer-sidecar disclaimer pattern noted: viewer output is visualization, never
  diagnosis (mirrors the Slicer license §4 posture).

## Attribution (compliance, not optional)

- OHIF MIT notice preserved in module NOTICE + CHANGELOG line. No credit-stripping.

## Test plan (local)

- `test_imaging_study_crud` (clinic isolation: cross-clinic id → 404, L1).
- Metadata extraction unit (pydicom on synthetic DICOM).
- Proxy auth tests (no token → 401, foreign clinic → 404).
- `removable=True` round-trip uninstall test.
- `dev-verify.sh --fast` + `--with-pytest --module imaging_viewer`; `/review` 0 blocks.

## Open spike questions (Phase 2) — RESOLVED 2026-09-03

1. **Proxy vs sidecar → PROXY wins.** `media` storage layout is
   `{clinic_id}/{patient_id}/{YYYY-MM}/{uuid}.{ext}`
   (`media/service.py:37-44`), clinic-scoped on disk AND in DB
   (`Document.clinic_id`, every query filtered). A proxy that resolves the
   document via a clinic-filtered DB lookup then `storage.retrieve()` is safe,
   simple, and needs no new ops surface. No Orthanc/dcm4chee sidecar in MVP.
   Proxy speaks minimal DICOMweb: QIDO `/studies` (JSON) + WADO
   `/studies/{uid}/series/{uid}/instances/{uid}/frames/{n}` (bytes) — just
   enough for the OHIF data source config.
2. **iframe vs npm embed → IFRAME wins.** OHIF v3 is React; iframe +
   postMessage isolates it from the Nuxt/Vue host. Pinned static build
   `v3.12.14` served from the module frontend `public/ohif/` dir, config
   pointing at our proxy. MIT notice kept alongside the build.
3. **pydicom is NOT a backend dep** (checked `pyproject.toml` + import) —
   the build adds `pydicom>=3.0` to `backend/pyproject.toml` dependencies.
