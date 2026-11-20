---
module: media
last_verified_commit: 0000000
---

# Media — technical overview

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Auto-discovered facts about the `media` module. See the module's
own notes at `backend/app/modules/media/CLAUDE.md` for context
the scaffold could not infer.

## API surface

- `DELETE /api/v1/media/attachments/{attachment_id}`
- `DELETE /api/v1/media/documents/{document_id}`
- `DELETE /api/v1/media/documents/{document_id}/pair`
- `GET /api/v1/media/attachments`
- `GET /api/v1/media/documents/{document_id}`
- `GET /api/v1/media/documents/{document_id}/download`
  Requests without a variant are recorded as views. Use `variant=full`
  for an explicit download that creates a separate access event.
- `GET /api/v1/media/patients/{patient_id}/documents`
- `GET /api/v1/media/patients/{patient_id}/photos`
- `PATCH /api/v1/media/documents/{document_id}/photo-metadata`
- `POST /api/v1/media/attachments`
- `POST /api/v1/media/documents/{document_id}/pair/{other_id}`
- `POST /api/v1/media/patients/{patient_id}/documents`
- `POST /api/v1/media/patients/{patient_id}/photos`
- `PUT /api/v1/media/documents/{document_id}`

## Frontend

_This module ships no Nuxt pages._

## Permissions

`documents.read`, `documents.write`, `attachments.read`, `attachments.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** `patient.archived`

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/media/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
