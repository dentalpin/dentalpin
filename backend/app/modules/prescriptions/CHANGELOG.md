# Changelog — prescriptions

## Unreleased

- Maintainer round 3: active-only allergies in the safety banner,
  readable interaction flags, locale-aware PDFs with full-address
  letterhead and DRAFT/CANCELLED marks, prescriber license settings
  section, stored-compliance hook wiring (`enhance_pdf_data` +
  `get_required_fields`), issue/cancel confirmations with error
  toasts, PDF download via `api.raw()`, nav entry dropped (patient
  card + action are the entry points), draft tools accept items with
  mapped errors, uninstall gate covers cancelled-after-issued,
  glossary receta row.
- Declare `patients_clinical` + `medical_reference` in
  `manifest.depends` (review: service imports both; honest dependency).
- Agent tools no longer roll back the session on 404 (match the
  `agenda/tools.py` precedent: rollback only on `IntegrityError`).

- fix: import relative paths in the prescriptions page and summary card
  resolve to the layer composables (TS2307 in CI on current main).

- Initial module: drafts with free-text/catalog-soft lines, issue/cancel
  lifecycle with prescriber snapshot, country hook registry
  (`PrescriptionComplianceHook`), templates, prescriber profiles,
  allergy/interaction banner, PDF download, agent draft tools.
