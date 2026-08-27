# Documents module

Generates prescriptions, medical certificates, referral letters and
radiology requests as branded PDFs with configurable clinic letterhead
(name, logo, address, registration number). Depends on `patients`
(for patient demographics) and `medication_catalog` (for prescription
medication lookup).

## Public API

Routes mounted at `/api/v1/documents/`.

- `GET    /documents`                — list, filterable by patient/type/status, paginated; `documents.read`
- `GET    /documents/{id}`           — single document; `documents.read`
- `POST   /documents`                — create (draft); `documents.write`
- `PATCH  /documents/{id}`           — edit title/content/status; `documents.write`
- `DELETE /documents/{id}`           — soft-delete (archive); `documents.write`
- `POST   /documents/generate`       — render document as branded PDF; `documents.write`

## Dependencies

`manifest.depends = ["patients", "medication_catalog"]` — reads patient
demographics for the letterhead recipient, and reads the medication
catalog for prescription autofill. Cross-module FKs to `patients.id`
and `users.id` are in the migration.

## Tenancy

`GeneratedDocument` has its own `clinic_id` column and every lookup
filters on it. The seeder and all CRUD operations are scoped to the
calling clinic.

## Events

### Published

| Event | Payload | When |
| --- | --- | --- |
| `document.generated` | `{document_id, clinic_id, patient_id, document_type, title}` | After successful PDF generation |

`activity_journal` picks up `document.generated` for timeline entries.

### Consumed

None — the module does not subscribe to any events.

## Permissions

`documents.read`, `documents.write`. Default role grants:

- **admin**: full management.
- **dentist**: read + write — prescribers generate documents.
- **assistant**: read-only — can view but not create.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `generate_document` | WRITE | `DocumentService.create_document` + `DocumentService.generate_pdf` | `documents.write` |

Returns structured metadata only — no free prose — so it stays
cloud-eligible (no `exposes_free_text`).

## Lifecycle

- `installable=True`, `auto_install=False` (ships inactive, the admin
  activates from the module admin UI), `removable=True`.
- Own Alembic branch (`documents`), rooted independently on core
  `"0001"` — no cross-branch FK, so no `depends_on` needed.
- Uninstall round-trip test in `test_uninstall_roundtrip.py`.

## Frontend

Nuxt layer at `frontend/` with:
- Page: `/documents` — document list with type/status/patient filters.
- Modal: document creation and PDF generation.
- Navigation: sidebar entry gated on `documents.read`, order 75.

## CHANGELOG

See `./CHANGELOG.md`.
