---
module: documents
screen: documents
route: /documents
related_endpoints:
  - GET /api/v1/documents
  - POST /api/v1/documents
  - PATCH /api/v1/documents/{id}
  - DELETE /api/v1/documents/{id}
  - POST /api/v1/documents/generate
related_permissions:
  - documents.read
  - documents.write
related_paths:
  - backend/app/modules/documents/frontend/pages/documents/index.vue
---

# Documents

Found under the **Documents** sidebar entry (or from the patient file
tab). The list shows all generated documents for the clinic, ordered
by most recent.

## What you can do

- **Search** by document title (live, debounced).
- **Filter** by document type (prescription, certificate, referral,
  radiology request) or status (draft, generated, archived).
- **Create** a new document — pick the patient, type, title and
  fill in the type-specific content fields.
- **Edit** a document's title or content (drafts only).
- **Generate** — renders the document as a branded PDF with the
  clinic letterhead (name, logo, address, registration number). A
  generated document appears in the patient timeline.
- **Archive** (soft-delete) — hides the document from the active list
  but preserves the record for history.

## Document types

| Type | Description |
|---|---|
| **Prescription** | Medications with dose, frequency and duration |
| **Medical certificate** | Diagnosis, description and validity period |
| **Referral letter** | Referred-to professional, specialty and clinical summary |
| **Radiology request** | Exam type, region and clinical question |

## Who can use it

Admins and dentists can create and generate documents. Assistants
have read-only access. Other roles need to be granted
`documents.read` / `.write` explicitly from the module admin UI.
