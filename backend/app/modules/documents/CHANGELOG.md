# Changelog — documents module

## Unreleased

- fix(#828): "Download PDF" saved generated documents as `….pdf_` on Windows. The filename regex kept the closing quote of `filename="….pdf"`, and the browser replaced the `"` with `_`.

- Wrap patient metadata on generated PDFs so details stay within the page in LTR and RTL layouts.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- fix: date-only fields (`YYYY-MM-DD`) are parsed as local midnight
  (`parseDateOnly`, host `utils/wallClock.ts`) instead of `new Date(s)`, which
  is UTC midnight and rendered every such date one day early in zones behind
  UTC — all of the Americas.
- feat(#657): owns the `documents` GDPR erasure coverage scope
  (`get_erasure_contributors()`). Issued prescriptions, certificates and
  referrals are retained as clinical records (Art. 17(3)(c)/(h)). The
  module is `auto_install: False`, so a clinic that never installed it no
  longer sees a coverage claim for it at all — previously `gdpr`'s
  hardcoded `clinical` row covered these documents unconditionally.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer; Hindi document PDF labels.
- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- feat(i18n): Telugu (`te`) labels for the managed-document PDF.
- feat(#509): the managed-document PDF for `pt-BR` reuses the `pt` labels.

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
