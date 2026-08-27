# Changelog — documents module

## Unreleased

- feat(#228): Initial documents module — prescriptions, medical
  certificates, referral letters and radiology requests as branded PDFs.
- CRUD under `/api/v1/documents/` with patient/type/status filters,
  pagination, and soft-delete (archive).
- PDF generation endpoint (`POST /documents/generate`) with branded
  clinic letterhead (name, logo, address, registration number).
- `document.generated` event published on the event bus; consumed by
  `activity_journal` for timeline entries.
- Agent tool `generate_document` (WRITE, cloud-eligible — structured
  data only).
- `auto_install=False`, `removable=True`, own Alembic branch
  (`documents`), uninstall round-trip test.
- Default roles: admin full, dentist read+write, assistant read-only.
- Docs: technical overview/events/permissions pages, user manual en+es,
  module CHANGELOG, CLAUDE.md tools section.
- Frontend layer: document list page, creation/generation modal,
  sidebar navigation entry.
- i18n: en, es, de, hu locale keys for the module.
