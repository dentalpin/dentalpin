# Documents module

Generates prescriptions, medical certificates, referral letters and
radiology requests as branded PDFs with configurable clinic letterhead
(name, logo, address, registration number). Depends on `patients` for
the patient demographics block.

## Public API

Routes mounted at `/api/v1/documents/`.

- `GET    /documents`                — list, filterable by patient/type/status, paginated; `documents.read`
- `GET    /documents/{id}`           — single document; `documents.read`
- `POST   /documents`                — create (draft); `documents.write`
- `PATCH  /documents/{id}`           — edit title/content/status; `documents.write`
- `DELETE /documents/{id}`           — soft-delete (archive); `documents.write`
- `POST   /documents/generate`       — render document as branded PDF (WeasyPrint), persist under storage, flip to `generated`, publish `document.generated`; `documents.write`
- `GET    /documents/{id}/download`  — stream the generated PDF; 404 if never generated / file missing; `documents.read`
- `GET/PUT /documents/settings/letterhead` — letterhead overrides stored namespaced under `clinic.settings["documents"]["letterhead"]`; gated by core `admin.clinic.read`/`admin.clinic.write`; unset keys fall back to the clinic profile

## Informed consents

Clinic-owned templates are snapshotted into consent documents. Templates can
be archived (`is_active=false`, `POST /consent-templates/{id}/archive|unarchive`,
`documents.write`): the list hides them unless `?include_archived=true`, and
`create_consent` raises `ConsentConflictError` (409) for an archived template.
Existing consents are unaffected. Staff can
issue a 30-minute bearer link for signing or revocation. Link tokens are
stored as hashes and the document row is locked before consuming a link.
The token lives in the URL fragment and is sent to the API in the
Authorization header, keeping it out of request paths and access logs.
The original signature publishes the existing transactional `document.generated`
event; revocation does not publish a second generation event.
Unsigned consents may be edited, archived and rendered as previews; edits and
archiving invalidate all pending links under the same document lock. Archived
consents cannot receive new signing links. A signed consent cannot be edited,
archived or regenerated; its persisted
PDF is downloaded verbatim. Revocations have separate signatures, dates,
PDFs and SHA-256 hashes, without rewriting the original. The public page
uses no staff session. Evidence includes signer relationship, IP and user
agent. The migration is on the documents branch and is reversible.

The clinic-scoped `GET /consents/signature-status?patient_id=…` returns
signature and revocation evidence state for the patient card and records a staff view.
The signing link stores its PDF locale, defaulting to the clinic language;
rendered signature times use the clinic timezone and localized relationship.
`ConsentService` owns consent operations and raises domain errors; HTTP routes
translate those errors. The backend renders the handoff QR using the first configured `ALLOWED_ORIGINS`
entry; it returns the matching fragment URL and PNG data URL to staff.

## Dependencies

`manifest.depends = ["patients"]` — reads patient demographics for the
PDF body. The `doc_0001` migration FKs to `patients.id` (declared
`depends_on = ("pat_0003",)` — patients has no branch label) and
`users.id` (core). Prescription medication lines are free text; there
is no catalog coupling.

## Tenancy

`GeneratedDocument` has its own `clinic_id` column and every lookup
filters on it. `create_document` verifies the patient belongs to the
calling clinic (`PatientService.get_patient`) and returns `None`
otherwise — the router surfaces a 400, so a document can never
reference an out-of-clinic patient.

## PDF rendering (`pdf.py`)

- WeasyPrint via `asyncio.to_thread` (mirrors billing). Four templates
  keyed by `document_type`, all content escaped.
- Letterhead resolves `clinic.settings["documents"]["letterhead"]`
  first, falling back per-key to the clinic profile (name, address,
  phone, email, tax_id). `logo` is an inline data URL when set.
- `generate_pdf` renders **before** flipping status, so a broken
  document never publishes an event. The bytes are written to
  `storage/documents/{clinic_id}/{id}.pdf`; `file_path` is the
  relative path. `download_pdf` reads that file back (409/404 if not
  generated yet).
- Alias `pdf.py:DocumentPDFService` — never hand-render HTML elsewhere.
- **Every host locale renders** (#524). `_LABELS` carries all ten in
  `PDF_LOCALES`, the endpoint validates with `PDF_LOCALE_PATTERN`, and
  the page passes the UI locale. Arabic sets `dir="rtl"` on `<html>`,
  as billing's invoice does. Adding a locale to `PDF_LOCALES` without a
  label set here fails `tests/test_pdf_label_coverage.py`, which
  discovers every module shipping a `pdf.py`. Clinical text the user
  typed is reproduced verbatim — only the captions are localized.

## Events

### Published

| Event | Payload | When |
| --- | --- | --- |
| `document.generated` | `{document_id, clinic_id, patient_id, document_type, title, created_by?}` | After successful PDF render **and** file write (transactional, `db=db`) |

`activity_journal` picks up `document.generated` for timeline entries.

### Consumed

None — the module does not subscribe to any events.

## Permissions

Module permissions: `documents.read`, `documents.write`. Default role
grants (from `manifest.role_permissions`):

- **admin**: full management.
- **dentist**: read + write — prescribers generate documents.
- **assistant**: read-only — can view but not create.

Letterhead settings reuse the core `admin.clinic.read`/`admin.clinic.write`
permissions (clinic-profile concern), not a module permission.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `generate_document` | WRITE | `DocumentService.create_document` + `DocumentService.generate_pdf` | `documents.write` |

`document_type` is a `Literal` constrained to the four supported
types; `created_by` is attributed via `ctx.supervisor_id` (the human
in the loop, same convention as `agenda`/`payments`). Returns
structured metadata only — no free prose — so it stays cloud-eligible
(no `exposes_free_text`).

## Lifecycle

- `installable=True`, `auto_install=False` (ships inactive, the admin
  activates from the module admin UI), `removable=True`.
- Own Alembic branch (`documents`), rooted independently on core
  `"0001"` with `depends_on = ("pat_0003",)` — fresh installs order
  the patients chain before this module's patients FK.
- Uninstall round-trip test in `test_uninstall_roundtrip.py`.

## Frontend

Nuxt layer at `frontend/` with:
- Page: `/documents` — document list with type/status/patient filters
  and a download action on generated rows.
- Modal: document creation with a server-search patient picker
  (UInputMenu pattern), client-side required-field gating, form inside
  the `#body` slot.
- Settings: letterhead editor card registered via
  `registerSettingsPage` (category `billing`).
- Navigation: sidebar entry gated on `documents.read`, order 75.

## Gotchas

- **An edit drops the PDF (#1006).** Changing the title or content of any
  document clears `file_path` and returns a generated one to draft. A
  `PATCH status=generated` is a 422 unless it restores an unedited document
  that still has its file; only `/generate` creates one.
- **GDPR erasure retains generated documents.**
  `erasure.DocumentsErasureContributor` owns the `documents` coverage
  scope (ADR 0038, #657) and writes nothing: a prescription or
  certificate must match the copy handed to the patient or the pharmacy
  (Art. 17(3)(c)/(h)). `content` is a free-form JSONB snapshot, so all
  three erasure categories are declared. Because the module is
  `auto_install: False`, a clinic that never installed it gets no
  `documents` coverage row at all — the registry only collects from active
  modules.

## CHANGELOG

See `./CHANGELOG.md`.

Staff evidence views and signed or revocation PDF downloads use the core
`RecordPatientAccess` dependency from #903. The public bearer-link flow has
no staff user; signing evidence records the signer, date, IP and user agent.
