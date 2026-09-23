# Changelog — imaging_viewer

## Unreleased

- fix: standalone `patient_id`/`document_id`/`study_id` indexes mirrored in
  `iv_0001`–`iv_0003` (model↔migration parity, L33); full 10-locale layer
  (fr/de/pl/it/ta/hu/ar/pt); `numpy` deferred to the `imaging_ai` PR.

- Human annotation overlays (T2): ruler (server-computed mm from pixel
  spacing, absent-never-guessed), freehand, notes on studies; normalized
  0-1 coordinates, originals immutable, archive-cascades. Display rules per
  `docs/technical/pano-overlay-design.md`. New `imaging_annotations`
  table (`iv_0003`), `list_study_annotations` agent tool.

- RVG watch-folder import (T1): content-hash dedup scan, DICOM-identity
  patient matching (national_id/DOB/name scoring, ambiguity-safe), approval
  queue UI on `/imaging`, approved identity links for auto-import, 90s
  scheduler tick + manual scan endpoint. New `rvg.read`/`rvg.write`
  permissions, `RvgLink`/`RvgImport` tables (`iv_0002`), `list_rvg_imports`
  agent tool. Design: `docs/technical/rvg-import-design.md`.
- Initial module: DICOM study index on media documents + clinic-scoped frame
  proxy + embedded OHIF viewer page (`v3.12.14`, MIT — see `NOTICE.md`).
- `imaging.study_indexed` event (emitted) + `media.photo_uploaded` auto-index
  and `patient.archived` cascade (consumed).
- DICOMweb-minimal façade (`GET /dicomweb/studies`, WADO frame path) for the
  vendored OHIF build (`frontend/public/ohif/`: config + build script; dist
  itself stays untracked).
