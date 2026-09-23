# Changelog — imaging_ai

## Unreleased

- fix: `noPatientHint` drops the `<uuid>` placeholder (vue-i18n build
  rejects HTML-like messages).
- fix: standalone `patient_id`/`study_id` indexes mirrored in `aij_0001`
  (model↔migration parity, L33); full 10-locale layer.

- Initial module: AI segmentation job queue over imaging studies
  (`nnUNetv2_predict` subprocess runner behind the `Runner` protocol),
  terminal-state audit trail, artifact ingestion as media documents,
  `imaging.ai_job_done` event. Weights CC-BY-4.0, CLI Apache-2.0 —
  see `NOTICE.md`.
- Second backend `pano`: `dental-pano-ai` (MIT) `main.py` wrap with DICOM→PNG
  rendering; unknown backends answer 422.
- Third backend `ocr`: `tesseract` CLI sidecar producing `ocr.txt`
  transcripts (paired text artifacts; blank images succeed artifact-free).
  Operator setup + attribution in `NOTICE.md`.
- `queued_by` nullable: the agent tool path carries no authenticated
  identity (L25) so it queues unattributed; the HTTP route still
  attributes the requesting user.
