# Changelog — documents module

## Unreleased

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer; Hindi document PDF labels.

- fix(#524): the managed-document PDF renders in every host locale.
  `_LABELS` held only `es`/`en`, the endpoint's pattern was `^(es|en)$`
  and the frontend sent no `locale` at all — so every clinic, in every
  language, got Spanish referral letters and medical certificates with
  no way to change it. Eight label sets added (overlapping terms lifted
  verbatim from the prescriptions and billing sets so a clinic's
  paperwork reads consistently), `PDF_LOCALE_PATTERN` on the endpoint,
  `dir="rtl"` for Arabic as billing already does, and the page now
  passes the UI locale.

- Follow-up: drop dead `TEMPLATE_MAP` (service.py) / `_DOC_NAMES`
  (pdf.py); roundtrip test docstring states the real `depends_on`.
- feat(#232): sidebar entry grouped under the Clinical header (`nav.section` "clinical").
- feat(i18n): Arabic (`ar`) locale for the module's frontend layer.
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
- Real PDF rendering in `pdf.py` (WeasyPrint off the event loop, four
  type-specific templates, escaped content). `generate_pdf` renders and
  persists the file under `storage/documents/{clinic_id}/` before
  flipping status and publishing the event.
- `GET /documents/{id}/download` streams the generated file as an
  `application/pdf` attachment (never-generated → 409, missing file →
  404).
- Letterhead settings endpoints (`GET/PUT /documents/settings/letterhead`)
  gated by core `admin.clinic.*`, persisted namespaced under
  `clinic.settings["documents"]["letterhead"]` with per-key fallback to
  the clinic profile; letterhead editor card on the settings page.
- Typed content schemas wired into `DocumentCreate` (validated against
  the document-type schema, dates normalized to JSON-safe ISO strings).
- `create_document` verifies the patient belongs to the caller's clinic
  (400 otherwise); tool args constrain `document_type` to a `Literal`
  and attribute `created_by` via `ctx.supervisor_id`.
- Router path params typed as `uuid.UUID` (malformed IDs → 422);
  removed `medication_catalog` from `depends` (never consumed).
- `doc_0001` declares `depends_on = ("pat_0003",)` so fresh installs
  order the patients chain before the `patients.id` FK.
- PDF storage honors `settings.TESTING` with a process-wide temp root
  (mirrors the media module), fixing CI runs that execute outside the
  compose `/app/storage` mount.
