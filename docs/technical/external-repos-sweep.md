# External repos sweep — Groups C/D/E + AI weights (verified 2026-09-03)

> Labels: **Stream** = workstream (1 imaging, 3 booking); **T/B** =
> tier intakes (§B of the imaging plan: T = code, B = weights/data,
> numbered); **Group** = repo cluster by purpose (C orthodontic apps,
> D PMS/booking, E marketing templates).
>
> Companion notes (§B1a/B1b) live on the imaging branches not yet
> merged. Every row below was verified live via the GitHub API `license`
> endpoint (or Zenodo API for weights) on 2026-09-03. Re-verify before any
> push — licenses can change.
>
> Rule (non-negotiable, candidate for an ADR — decision pending):
> no license file = all rights reserved = **no code
> copied, build-similar only**. MIT/Apache-2.0 = usable **with the copyright
> notice preserved**. GPL/NC/custom-restricted = **no code**.

## Weights — B1b (Stream 1 input)

| Artifact | License (verified) | Verdict |
|---|---|---|
| Zenodo `Dataset112_DentalSegmentator_v100.zip` (DOI `10.5281/zenodo.10829675`, 230 MB) | **CC-BY-4.0** (open, attribution via paper citation) | ✅ Usable as operator-downloaded weights. Cite Dot et al. 2024 + Isensee nnU-Net 2021. **V1 unblocked with real weights.** |

## Group C — orthodontic apps (reference only, feeds #270 design)

| Repo | License | Verdict |
|---|---|---|
| `lopo12123/Orthodontic-platform` | none | build-similar only |
| `donovanhiland/OrthodonticApp` | none | build-similar only |
| `rahul1947/Orthodontist-Expert-System` | **MIT** (© 2019 Rahul Nalawade) | usable with notice; still treat as design reference (student-grade) |
| `Kruthikas27/AI-Based-Validation-System-for-Orthodontic-Braces-Placement` | none | build-similar only |
| `davidegironi/dentned` | none | build-similar only |

## Group D — PMS / ERP / booking (booking-UX patterns for Stream 3)

| Repo | License | Verdict |
|---|---|---|
| `alexcorvi/apexo` | **MIT** (© 2019 Alex Corvi) | parity study only (separate PMS, never embedded) |
| `alselawi/apexo-flutter` | **GPL-3.0** | excluded, no code |
| `odonto-facil/odontofacil-dental-erp` | none | build-similar only |
| `acevedo-daniel/dms-demo` | **MIT** (© 2026 Daniel Acevedo) | usable with notice |
| `muhammedmaahir68-droid/dental-clinic-management-system` | none | build-similar only |
| `Hezarani/dentrx` | **MIT-text** + clinical disclaimer (API: NOASSERTION, file governs) | usable with notice; keep the not-medical-advice disclaimer posture |
| `Raju53/Nacre-Dentals-Online-Appointment-Booking-Application` | none | build-similar only |
| `Tzesh/Denpointment` | none | build-similar only |
| `hbapte/dentrw-alx` | **MIT** (© 2024) | usable with notice |

## Group E — marketing site templates (portal styling inspiration only)

MIT (usable with notice): `themixlyweb/nextjs-dental-website-template`,
`harshitdev-wq/dentist-clinic-website`, `lat0s/FlossophyUI` (Apache-2.0).
Custom/restricted — no code: `vin-jex/dent-clack` (Dent-Clack License v1.0:
public distribution non-commercial only → build-similar only).
No license — no code: `AshisChetia/DentaPremium`, `alaeddineazri/Dentist-Project`,
`Bharadwaja-sahoo/Dental-site`, `Omareeo/dentist-website-with-PHP-Laravel`,
`uttamsdev/dentist-application`, `ahmed-ali-codes/smilecraft-dental-site`,
`tnaomi/dentist`, `ganraj21/Dental_Clinic`, `sohelrana1831/AYSHA-DENTAL-CARE`,
`codewithsadee/dentelo`.

## Tier-1 pano backends (adjudicated 2026-09-03 — feeds the pano Runner)

| Candidate | Code | Weights / data | Verdict |
|---|---|---|---|
| `stmharry/dental-pano-ai` | **MIT** ✅ | S3 tarball, no stated terms; Docker image published; CPU-only | **PICK.** CLI wrap, weights operator-provided. Cite Wang et al. arXiv:2502.10277. |
| `ibrahimethemhamamci/HierarchicalDet` | **MIT** ✅ | DENTEX data **CC BY-SA 4.0** (open, share-alike) | Runner-up. Cite Hamamci MICCAI 2023. |
| `NoahOksuz/DentalXrayAI` | **Apache-2.0** ✅ | `best.pt` personal link, no terms; **ultralytics is AGPL** | Feasible with CLI-boundary containment; deferred. |
| `IvisionLab/deep-dental-image` | **MIT** ✅ | weights unknown | Deferred; operator-provided gate. |
| `clemkoa/tooth-detection` | **MIT** ✅ | dataset + model **explicitly NOT shared** | No backend possible; pipeline idea only. |
| `ibrahimethemhamamci/DENTEX` | **none** (ledger "MIT code" corrected) | data CC BY-SA 4.0 | Build-similar + benchmark reference only. |
| `limhoyeon/ToothGroupNetwork`, `LucasKre/dilated_tooth_seg_net`, `IvisionLab/dental-image`, `Loki-Silvres/Dental-Disease-Detection`, `sdmadhav/CBCT_Dental`, `prince0310/Smart-CBCT…`, `ErdanC/…bone…`, `Maxlo24/ALI_CBCT`, `Ash2617/DICOM_VIEWER` | none | — | Build-similar only. |
| `AImageLab-zip/ToothFairy2-Benchmark` | none | — | Benchmark reference only. |
| `coolleafly/VDING` | **GPL-3.0** ❌ (newly verified) | — | Excluded (ledger B4). |

Full per-repo notes ship with the `imaging_ai` rebuild (not yet on
main).

## Scoreboard

- 40 swept: 13 permissive (MIT/Apache, usable with notice) · 1 custom-restricted ·
  3 excluded (GPL) · 23 unlicensed-or-NC (build-similar/ideas only).
- Net code-grade inputs: OHIF (B1a), nnU-Net CLI + CC-BY weights (B1b),
  dental-pano-ai (pano Runner), HierarchicalDet/DentalXrayAI/deep-dental-image
  (standby backends), apexo (parity study), dms-demo/dentrx/dentrw-alx +
  rahul1947 expert system + 3 templates (available with notice). Everything
  else is ideas-only.
