# Third-party notices — imaging_ai

This module shells out to nnU-Net (never vendored) and consumes its
pretrained weights (operator-downloaded, never shipped). Per their licenses,
attribution is preserved here. No third-party code is copied into this repo.

## nnU-Net CLI (https://github.com/MIC-DKFZ/nnUNet) — Apache-2.0

Used as an external `nnUNetv2_predict` binary only. If you use it, cite:

> Isensee F, et al. nnU-Net: a self-configuring method for deep learning-based
> biomedical image segmentation. Nat Methods. 2021;18(2):203-211.
> doi:10.1038/s41592-020-01008-z

## DentalSegmentator weights (DOI 10.5281/zenodo.10829675) — CC-BY-4.0

`Dataset112_DentalSegmentator_v100.zip` (~230 MB), operator-provided via the
weights dir. If you use the model, cite:

> Dot G, et al. DentalSegmentator: robust open source deep learning-based CT
> and CBCT image segmentation. Journal of Dentistry (2024).
> doi:10.1016/j.jdent.2024.105130

## dental-pano-ai (https://github.com/stmharry/dental-pano-ai) — MIT

Pano-findings backend (`PanoRunner` shells to its `main.py`; operator-provided
checkout + S3 weights, neither vendored). If you use it, cite:

> Wang Y-C C, et al. Artificial Intelligence to Assess Dental Findings from
> Panoramic Radiographs — A Multinational Study. arXiv:2502.10277 (2025).

## Tesseract OCR (https://github.com/tesseract-ocr/tesseract) - Apache-2.0

Receipt/text backend (`OcrRunner` shells to the `tesseract` CLI; never
vendored). Operator setup on the AI host: install Tesseract plus the needed
language packs (e.g. `apt install tesseract-ocr tesseract-ocr-spa`), point
`DENTALPIN_TESSERACT_BIN` at the binary only if it is off-PATH, and set
`DENTALPIN_TESSERACT_LANG` (default `eng`). Transcripts ingest as paired
`.txt` artifacts for clinician review — never auto-applied.
