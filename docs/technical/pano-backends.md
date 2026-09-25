# Pano detection backends — weights verdicts (verified 2026-09-03)

> Tier-1 pano shortlist for the second `imaging_ai` Runner backend. Code
> licenses via GitHub API; weights/data terms via project READMEs. Rule:
> unlicensed weights = operator-provided, never vendored; no shared model =
> no backend (build-similar only).

| Candidate | Code | Weights / data | Verdict |
|---|---|---|---|
| `stmharry/dental-pano-ai` | **MIT** ✅ | S3 tarball, **no stated license**; Docker image published; CPU-only libs | **PICK for Phase B.** CLI/docker wrap; weights operator-provided. Cite Wang et al. arXiv:2502.10277. |
| `ibrahimethemhamamci/HierarchicalDet` | **MIT** ✅ | DENTEX data **CC BY-SA 4.0** (open, share-alike — ledger "NC" corrected) | Runner-up. Share-alike binds distributed derivatives; use-as-service is fine. Cite Hamamci MICCAI 2023 + DENTEX arXiv:2305.19112. |
| `NoahOksuz/DentalXrayAI` | **Apache-2.0** ✅ | `best.pt` via personal link, no terms; **ultralytics is AGPL** — CLI-boundary containment only | Feasible with AGPL care; deferred behind the pick. |
| `IvisionLab/deep-dental-image` | **MIT** ✅ | weights unknown | Deferred; same operator-provided gate. |
| `clemkoa/tooth-detection` | **MIT** ✅ | **dataset + model explicitly NOT shared** (privacy) | **No backend possible.** Build-similar (Faster R-CNN pano pipeline idea) only. |
| `ibrahimethemhamamci/DENTEX` | **none** (ledger "MIT code" corrected) | data CC BY-SA 4.0 | Build-similar only (benchmark reference). |
| `limhoyeon/ToothGroupNetwork`, `LucasKre/dilated_tooth_seg_net`, `IvisionLab/dental-image`, `Loki-Silvres/Dental-Disease-Detection`, `sdmadhav/CBCT_Dental`, `prince0310/Smart-CBCT…`, `ErdanC/…bone…` | none | — | Build-similar only. |
| `AImageLab-zip/ToothFairy2-Benchmark` | none | — | Benchmark reference only. |
| `coolleafly/VDING` | **GPL-3.0** ❌ | — | Excluded (ledger B4). |
