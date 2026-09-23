# AI imaging host — operator runbook

> Local-only until the imaging arc ships; then this becomes the maintained
> ops page for the viewer + AI backend hosts. Audience: the clinic's technical
> operator, not front-desk staff.

## What runs where

| Piece | Runs in | Needs on the host |
|---|---|---|
| Study index + frame proxy + DICOMweb façade | backend container | `pydicom` + `numpy` (declared in `backend/pyproject.toml`) |
| OHIF interactive viewer | browser iframe → vendored dist | one-time `frontend/public/ohif/build-from-source.sh` (pinned `v3.12.14`) |
| nnU-Net CBCT jobs (`nnunet` backend) | AI host (same machine OK for CPU, GPU box for speed) | `nnUNetv2_predict` on PATH, torch, ~230 MB weights |
| Pano jobs (`pano` backend) | AI host | `dental-pano-ai` checkout (`DENTALPIN_PANO_APP`) + its S3 weights |

Without the AI host pieces, jobs fail gracefully with actionable errors —
nothing crashes, nothing retries blindly.

## OHIF dist build (one-time, ~20–40 min)

OHIF publishes **no downloadable viewer bundle** (their `v3.12.14` release
carries zero assets — verified via API), so the interactive viewer cannot be
fetched; it is compiled once from source. `StudyViewer.vue` falls back to
the original-file download until this is done — everything else works
without it, and CI never needs it.

1. On any machine with **node ≥ 22 + yarn**, run
   `backend/app/modules/imaging_viewer/frontend/public/ohif/build-from-source.sh`.
   It clones the pinned tag, builds, and drops `dist/` next to the committed
   `ohif-config.js` (which points the viewer at our DICOMweb proxy under the
   same JWT session — no separate credentials).
2. Serve that directory at `/ohif/` (see the module README in `public/ohif/`).
3. Verify: open any study — it renders in the viewer instead of the fallback.
   That single page-load is the whole acceptance test.
4. Never commit `dist/` (untracked build output, like `node_modules`);
   re-run only when we re-pin OHIF. MIT notice already in module `NOTICE.md`.

## nnU-Net setup

1. Install torch + nnU-Net v2 on the AI host (`pip install nnunetv2 torch`
   per https://github.com/MIC-DKFZ/nnUNet — Apache-2.0).
2. Download `Dataset112_DentalSegmentator_v100.zip` (DOI
   `10.5281/zenodo.10829675`, CC-BY-4.0) and unpack where the runner finds
   it. Cite Dot et al. 2024 + Isensee et al. 2021 (see module NOTICE.md).
3. Verify: `nnUNetv2_predict --help` exits 0 **as the backend user**.

CPU-only hosts work but are slow (upstream warns); refusal/confirmation
wording surfaces in the job log, never as a traceback.

## Pano setup

1. Clone `dental-pano-ai` (MIT) somewhere stable; download its S3 weights
   tarball into the checkout (no stated terms — operator-provided, never
   vendored). Cite Wang et al. arXiv:2502.10277.
2. `export DENTALPIN_PANO_APP=/path/to/dental-pano-ai` in the backend
   environment (compose file or systemd unit — wherever the backend runs).
3. Verify: queue a pano job on a test study; expect `done` + one overlay
   document paired to the source.

## Smoke check (zero to viewed study + completed job)

1. Upload a `.dcm` file to a test patient (accepted MIME now includes
   `application/dicom` — no config change needed).
2. Confirm the study appears under `/imaging?patient_id=<uuid>` and its
   metadata shows (frame proxy serves bytes).
3. Queue an AI job; poll to `done`; open the artifact overlay document.
4. If the interactive viewer is vendored, confirm the study renders in it.

## Quotas & safety

- AI output is a visualization aid, never a diagnosis (captioned in both
  locales on every surface).
- Job rows are never deleted (audit trail); `log_excerpt` is bounded at
  4000 chars; runner timeouts default 60 min (nnU-Net) / 30 min (pano).
