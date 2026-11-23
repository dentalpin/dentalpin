---
module: documents
---

# documents — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints / tools |
|---|---|---|
| `documents.read` | List, view, download, consent evidence | `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/download`, `GET /api/v1/documents/consent-templates` (active only; `?include_archived=true` adds archived), `GET /api/v1/documents/consents/signature-status`, `GET /api/v1/documents/consents/{id}/evidence`, `GET /api/v1/documents/consents/{id}/evidence/{purpose}/download` |
| `documents.write` | Create, edit, archive, generate, manage consents | `POST /api/v1/documents`, `PATCH /api/v1/documents/{id}`, `DELETE /api/v1/documents/{id}`, `POST /api/v1/documents/generate`, `POST /api/v1/documents/consent-templates`, `PUT /api/v1/documents/consent-templates/{template_id}`, `POST /api/v1/documents/consent-templates/{template_id}/archive`, `POST /api/v1/documents/consent-templates/{template_id}/unarchive`, `POST /api/v1/documents/consents`, `POST /api/v1/documents/consents/{id}/links`, agent tool `generate_document` |
| `admin.clinic.read` | View letterhead overrides | `GET /api/v1/documents/settings/letterhead` |
| `admin.clinic.write` | Persist letterhead overrides | `PUT /api/v1/documents/settings/letterhead` |

> The letterhead settings endpoints reuse the core
> `admin.clinic.*` clinic-profile permissions (same gate as the
> budget settings endpoints) — clinic branding is a clinic-profile
> concern, not a per-document one.

Default role mapping:

- **admin**: full management (documents are admin territory).
- **dentist**: read + write — prescribers generate prescriptions,
  certificates, referrals and radiology requests.
- **assistant**: read-only — can view documents for reference but
  cannot create or generate.
- other roles: none out of the box. Clinics can widen from the
  module admin UI.

The public signing routes `GET /api/v1/documents/public/consents/current` and
`POST /api/v1/documents/public/consents/current/sign` require a valid short-lived
bearer token, not a staff permission. Their scope is one consent and operation.
