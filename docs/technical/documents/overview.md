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
`activity_journal`).

Cross-module reads: `patients` (for demographics / letterhead
recipient) and `medication_catalog` (for prescription medication
lookup / autofill). No cross-module writes.

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
1. Fetches the document + clinic letterhead configuration.
2. Renders a Jinja2 template with the document content and clinic
   branding.
3. Produces a PDF via WeasyPrint (or similar).
4. Stores the file at `storage/documents/{clinic_id}/{document_id}.pdf`.
5. Marks the document as `generated` and publishes `DOCUMENT_GENERATED`.

## Data model

- `generated_documents` — `id`, `clinic_id`, `patient_id`,
  `document_type`, `title`, `status`, `content` (JSONB), `file_path`
  (nullable), `created_by` (nullable FK to `users.id`), timestamps.

## Lifecycle

`installable=True`, `auto_install=False` (ships inactive, the admin
activates it from the module admin UI), `removable=True`. Own Alembic
branch (`documents`), rooted independently on core `"0001"` — no
cross-branch FK, so no `depends_on` needed.
