---
module: documents
screen: documents
route: /documents
last_verified_commit: 10085df
related_endpoints:
  - GET /api/v1/documents
  - POST /api/v1/documents
  - PATCH /api/v1/documents/{id}
  - DELETE /api/v1/documents/{id}
  - POST /api/v1/documents/generate
  - GET /api/v1/documents/{id}/download
  - GET /api/v1/documents/settings/letterhead
  - PUT /api/v1/documents/settings/letterhead
related_permissions:
  - documents.read
  - documents.write
related_paths:
  - backend/app/modules/documents/frontend/pages/documents/index.vue
  - backend/app/modules/documents/frontend/components/DocumentCreateModal.vue
  - backend/app/modules/documents/frontend/components/settings/DocumentsLetterheadPage.vue
---

# Documents

Found under the **Documents** sidebar entry (or from the patient file
tab). The list shows all generated documents for the clinic, ordered
by most recent.

## What you can do

- **Filter** by document type (prescription, certificate, referral,
  radiology request) or status (draft, generated, archived).
- **Create** a new document — pick the patient (with a live server
  search), type, title and fill in the type-specific content fields.
- **Edit** a document's title or content (drafts only).
- **Generate** — renders the document as a branded PDF with the
  clinic letterhead (name, logo, address, registration number). A
  generated document appears in the patient timeline. The PDF's field
  labels and its title (*Referral letter*, *Medical certificate*, …)
  follow the language you are using the app in — all ten of them, with
  Arabic laid out right-to-left. Clinical text you typed is reproduced
  as written; it is not translated.
- **Download** — save the generated PDF from a `generated` row.
- **Archive** (soft-delete) — hides the document from the active list
  but preserves the record for history.

## Document types

| Type | Description |
|---|---|
| **Prescription** | Medications with dose, frequency and duration |
| **Medical certificate** | Diagnosis, description and validity period |
| **Referral letter** | Referred-to professional, specialty and clinical summary |
| **Radiology request** | Exam type, region and clinical question |

## Clinic letterhead

Under **Settings → Billing → Document letterhead** the clinic can
override the branding used on generated PDFs: header name, address,
phone, email, registration/license number and a logo image. Fields
left blank fall back to the clinic profile.

## Who can use it

Admins and dentists can create and generate documents. Assistants
have read-only access. Other roles need to be granted
`documents.read` / `.write` explicitly from the module admin UI.
The letterhead editor requires `admin.clinic.write`.

## Informed consents

From the patient record, create or select a clinic template and create the consent. Open the link on the tablet without a staff session; it expires after 30 minutes and accepts one signature. The patient or representative provides their name and relationship and draws their signature. Download the signed PDF from the record. To revoke, create a revocation link and collect a new signature; the original consent remains intact. Corrections require a new consent.

Before signing, the consent can be edited, archived or rendered as a preview. Editing or archiving invalidates outstanding links; create a new link after editing.
