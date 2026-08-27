---
module: documents
---

# documents — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints / tools |
|---|---|---|
| `documents.read` | List, view | `GET /api/v1/documents`, `GET /api/v1/documents/{id}` |
| `documents.write` | Create, edit, delete (archive), generate PDF | `POST /api/v1/documents`, `PATCH /api/v1/documents/{id}`, `DELETE /api/v1/documents/{id}`, `POST /api/v1/documents/generate`, agent tool `generate_document` |

Default role mapping:

- **admin**: full management (documents are admin territory).
- **dentist**: read + write — prescribers generate prescriptions,
  certificates, referrals and radiology requests.
- **assistant**: read-only — can view documents for reference but
  cannot create or generate.
- other roles: none out of the box. Clinics can widen from the
  module admin UI.
