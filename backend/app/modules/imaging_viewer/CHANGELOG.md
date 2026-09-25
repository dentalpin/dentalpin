# Changelog — imaging_viewer

## Unreleased

- fix: the viewer fetched the render through a relative `<img src>`, which
  404s whenever the API is on another origin (docker-compose, Coolify). The
  PNG now arrives as an object URL via `api.raw()`, the credentialed
  same-origin pattern from the media layer's `getDocumentBlobUrl`; the URL is
  revoked on study change and unmount. `StudyViewer` is gone (it rendered the
  same PNG a second time as `AnnotationPanel` already did); its compliance
  "visualization only, never a diagnosis" note now lives under the canvas.
- fix: ruler mm was the normalized point distance times a single pixel-spacing
  value, so it ignored the image's aspect ratio and reported a plausible but
  wrong number (0.35 mm for a 100x200 image measured corner-to-corner at
  0.5 mm). It now scales each axis by its own pixel count and applies
  `PixelSpacing`'s `[row\column]` order: 111.8 mm for that image. Still absent,
  never guessed, when Rows/Columns or spacing are missing.
- fix: a scanned RVG file was moved to `processed/` by the scan, while
  approve only looked in the clinic root, so every queued approval answered
  404 "Source file no longer in the watch folder" and the queue's approve
  button was dead. Files awaiting a human decision now park in `pending/`;
  approve reads from there (with `processed/` and the root probed for rows
  created by earlier scans) and retires the file to `processed/` once decided.
  Covered by a new scan -> approve HTTP test.
- fix: `GET /studies/{id}/render` decoded PNGs synchronously inside the async
  handler, blocking the event loop; rendering now runs via `asyncio.to_thread`
  (the `budget`/`billing` PDF pattern).
- fix: a crafted DICOM header could claim an enormous pixel grid and take the
  worker out with an OOM kill (no traceback, no response). The render refuses
  grids over 80 MP (generous for a stitched pano, ~640 MB of float64 avoided)
  with a clean 422, checked from Rows x Columns before any array exists.
- fix: the photo picker hid `.dcm` behind `accept="image/*"`, so DICOM could
  not be chosen even though the upload path accepts it; both inputs now list
  `.dcm`/`application/dicom`.
- Review round 2: backend PNG render (`GET /studies/{id}/render`,
  server-side windowing, 422 when undecodable) replaces the OHIF
  iframe + DICOMweb façade + frame proxy (all removed with their
  tests); annotation canvas draws over the PNG. Indexing is
  idempotent (unique clinic+document, 201 new / 200 existing);
  the upload handler is flush-only inside a savepoint with a single
  byte fetch (ADR 0019) and sniffs `DICM` for octet-stream uploads;
  RVG watch files handled by a tick go to `processed/`; `/imaging` has a
  patient picker; `rvg/scan` requires `rvg.write`; `study_date`
  parses from tags; timeline subscribes to `imaging.study_indexed`.
- fix: current `useApi` contract (`api.del`, `{ query }`) + `noUncheckedIndexedAccess`
  (`[noteAt]`, first-study guard) in the layer; `noPatientHint` drops the
  `<uuid>` placeholder (vue-i18n build rejects HTML-like messages).
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
