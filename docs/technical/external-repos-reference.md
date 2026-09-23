# External repos reference — imaging/AI integration candidates

> Local-only integration planning reference (ledger §7a). License verdicts below
> were verified live via the GitHub API `license` endpoints on 2026-09-03.
> Re-verify before any push: licenses can change between verification and ship.
>
> Compliance rule (non-negotiable): MIT/Apache-2.0/BSD-style code may be
> embedded or wrapped **only with its copyright + license notice preserved**
> (NOTICE/about-page + CHANGELOG line). GPL/NC/unlicensed code is never copied.
> "Build-similar" means reimplementing the *idea* in our own code — no
> attribution needed, no foreign code vendored.

## B1a. DICOM viewer (ledger verdict: full embed)

| Repo | License (verified) | Pinned | Verdict | Notes |
|---|---|---|---|---|
| `OHIF/Viewers` | **MIT** — `LICENSE` on `master`, Copyright 2018 Open Health Imaging Foundation | `v3.12.14` (latest release, 2026-09-03) | **Full embed, iframe + postMessage** | React + cornerstone, DICOMweb QIDO/WADO. Attribution required: keep MIT notice. Winner. |
| `Ash2617/DICOM_VIEWER` | **None** — no license file (API 404) = all rights reserved | — | **Build-similar only, no code** | Small demo viewer; usable as a WADO-proxy shape reference at most. Do not copy. |
| `denysdovhan/voxel-viewer` | **PolyForm Noncommercial 1.0.0** | — | **Excluded, no code** | Noncommercial-only; bars clinic use. Ledger B4. |

## B1b/B1c. CBCT segmentation sidecars (ledger verdict: partial via CLI)

| Repo | License (verified) | Verdict | Notes |
|---|---|---|---|
| `gaudot/SlicerDentalSegmentator` | **Apache-2.0** text in `LICENSE.txt` (`main`, © 2024) — API reports NOASSERTION, file content governs | **CLI/sidecar wrap, attribution kept** | nnU-Net based; quarantines torch deps outside the backend. |
| `DCBIA-OrthoLab/SlicerAutomatedDentalTools` | **3D Slicer License v1.0** (BSD-style + research-use/FDA disclaimer, attribution preservation required) | **CLI/sidecar only, with disclaimer** | §4: research-only, clinical use neither recommended nor advised — never present its output as diagnosis; keep attributions. |
| `KitwareMedical/SlicerCBCTToothSegmentation` | **Apache-2.0** (`LICENSE.txt` on `master`, © 2024 Kitware, Inc.) | **CLI/sidecar wrap, attribution kept** | Companion to the above. |
| `Maxlo24/ALI_CBCT` | **None** — no license file (API 404) = all rights reserved | **Build-similar only, no code** | Do not copy. |
| `SerdarHelli/Segmentation-of-Teeth-in-Panoramic-X-ray-Image-Using-U-Net` | **GPL-3.0** | **Excluded, no code** | Copyleft conflicts with BSL-1.1. Ledger B4. |

## Integration order (ledger §7c)

1. B1a OHIF embed first (this arc: `imaging_viewer` module).
2. B1b generic "AI job via CLI" pattern second, reusing the proxy + job plumbing.
3. Research-grade pano/AI repos (DENTEX etc.) stay build-similar, long-horizon.

## Corrections + Tier-1 pano adjudication (2026-09-03)

- `ibrahimethemhamamci/DENTEX` has **no license file** (API 404) — the old
  "MIT code" label is withdrawn; code and benchmark are build-similar only.
  Its *data* is CC BY-SA 4.0 per the HierarchicalDet README (open,
  share-alike binds distributed derivatives).
- `coolleafly/VDING` is **GPL-3.0** (verified) — ledger B4, no code.
- Full Tier-1 pano table (dental-pano-ai pick, HierarchicalDet, DentalXrayAI
  + AGPL-ultralytics flag, deep-dental-image, tooth-detection downgrade):
  `docs/technical/pano-backends.md` (ships with the `imaging_ai` branch).
- Groups C/D/E sweep (28 repos): `docs/technical/external-repos-sweep.md`
  (ships with the `pr/integration-docs` branch).
