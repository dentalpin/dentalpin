---
module: documents
---

# documents — overview

Generates prescriptions, medical certificates, referral letters and
radiology requests as branded PDFs with configurable clinic letterhead
(name, logo, address, registration number).

## What it is

Standard clinic-scoped CRUD over a flat `GeneratedDocument` list:
create, list (filterable by patient, document type and status,
paginated), get, update (partial via `exclude_unset`), delete
(soft-delete / archive). A `POST /documents/generate` endpoint
renders the document as a branded PDF and publishes
`DOCUMENT_GENERATED` on the event bus (consumed by
`activity_journal`), and `GET /documents/{id}/download` streams the
rendered file.

Clinic letterhead overrides are configurable per clinic via
`GET/PUT /documents/settings/letterhead` (stored namespaced under
`clinic.settings["documents"]["letterhead"]`).

Cross-module reads: `patients` (for the patient demographics block in
the PDF). No cross-module writes. Prescription medication lines are
free text entered in the form — there is no catalog coupling.

## Document types

| Type | Key content fields |
|---|---|
| `prescription` | diagnosis, medications (name/dose/frequency/duration/notes), notes |
| `medical_certificate` | diagnosis, description, recommendations, valid_from, valid_until |
| `referral` | referred_to, specialty, reason, clinical_summary, notes |
| `radiology_request` | exam_type, region, clinical_question, notes |

Content is stored as JSONB — each document type has a Pydantic schema
that validates the structure, but the column itself is schemaless for
forward compatibility.

## Integrity guarantees

- Documents are scoped per clinic (every query filters by `clinic_id`).
- Soft-delete via `status` column (`draft` → `generated` → `archived`).
- No hard deletes — document history is preserved.

## PDF generation

The generate endpoint:
1. Fetches the document + clinic + patient.
2. Resolves the letterhead from `clinic.settings["documents"]["letterhead"]`,
   falling back per-key to the clinic's native profile (name, address,
   phone, email, tax_id).
3. Renders an HTML template (`pdf.py`) with the document content,
   patient demographics and clinic branding — `body`-only if
   WeasyPrint is unavailable it falls back to raw HTML.
4. Renders via WeasyPrint off the event loop (`asyncio.to_thread`,
   same pattern as billing).
5. Persists the file at `storage/documents/{clinic_id}/{document_id}.pdf`
   and stores the relative `file_path` on the row — only after the
   render succeeds does the status flip to `generated`, so no event
   fires for a document without a real file behind it.
6. Publishes `DOCUMENT_GENERATED`.

`GET /documents/{id}/download` streams the persisted bytes back as an
`application/pdf` attachment (404 if the document was never generated
or the file is missing; documents the download doesn't re-render).

## Data model

- `generated_documents` — `id`, `clinic_id`, `patient_id`,
  `document_type`, `title`, `status`, `content` (JSONB), `file_path`
  (nullable), `created_by` (nullable FK to `users.id`), timestamps.

## Lifecycle

`installable=True`, `auto_install=False` (ships inactive, the admin
activates it from the module admin UI), `removable=True`. Own Alembic
branch (`documents`), rooted independently on core `"0001"`. The
initial migration FKs to `patients.id`; because `patients` has no
branch label of its own, `doc_0001` declares
`depends_on = ("pat_0003",)` (same pattern as
`patient_relationships.prel_0001`) so a fresh install orders the
patients chain first.

## Informed consents

Consent templates are scoped to the clinic and copied into each consent.
Staff create a 30-minute, single-use signing or revocation link. The public
endpoint only exposes that document. The link keeps its token in the URL
fragment, and the client sends it in the Authorization header rather than
the request path. Signing serializes on the document
row, stores independent evidence and writes the signed PDF once; SHA-256
is computed over those exact bytes. Downloads serve that file. Revocation
creates separate evidence and a PDF; the original is unchanged. Unsigned
consents may be edited, archived or rendered as previews. Editing or
archiving invalidates pending links under the document lock. The patient
card reads the evidence-backed signature state in one clinic-scoped query; archived
consents cannot receive new signing links. Regeneration does not unarchive
a consent. Signed consents cannot be
edited, archived or regenerated.

Staff evidence views and signed or revocation PDF downloads use the core
`RecordPatientAccess` dependency from #903. The public bearer-link flow has
no staff user; signing evidence records the signer, date, IP and user agent.
