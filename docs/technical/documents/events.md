---
module: documents
---

# documents — events

## Published

| Event | Payload | When |
|---|---|---|
| `document.generated` | `{document_id, clinic_id, patient_id, document_type, title, created_by?}` | After successful PDF generation in `DocumentService.generate_pdf` or the original signature in `ConsentService.sign_consent` (transactional, `db=db`); revocation does not publish |

`activity_journal` picks up `document.generated` to create a
timeline entry documenting the document creation.

### Why publish

Even though the documents module owns the row, subscribers need to
react without importing documents models:

- **activity_journal** — adds a "Document generated" entry to the
  patient timeline with the document type and title.
- **notifications** (future) — could notify the patient that a
  prescription or certificate is ready.
- **billing** (future) — could link a generated prescription to a
  budget or invoice.

## Consumed

The module consumes **no events**. It does not subscribe to any
event bus topics.
