# Pano overlay display contract — design record (Stream 4, design-only)

> Local-only design. No model weights, no training code, no NC data. This
> contract lets the `imaging_viewer` page render detection overlays the day
> licensed-data models exist. Overlays are visualization aids, never diagnoses.

## Artifact contract (what a future model backend must produce)

- Input: study id (DICOM bytes stay in `media` storage, resolved clinic-scoped).
- Output: `overlay_set` = list of `{label, tooth_fdi?, polygon|bbox, score}` +
  rendered PNG preview(s) ingested as `media` documents (kind `xray`,
  paired to the source study document).
- Transport: same `Runner` protocol as B1b (`imaging_ai` branch) with
  `backend="pano_overlay"`; job row carries `model_id + model_version` for
  audit (which weights produced this overlay, forever traceable).

## Display rules

- Overlays render as toggleable layers over the study frame; scores shown,
  never hidden thresholds.
- Every overlay view carries the model id/version + "visualization aid —
  never a diagnosis" caption (both locales).
- Dentist role required to request; read roles may view completed overlays.

## Blocked on

Licensed pano training data + a permissively-licensed reference model.
Until then: contract only, zero code.
