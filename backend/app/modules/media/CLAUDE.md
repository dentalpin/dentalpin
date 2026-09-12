# Media module

Patient documents, images, file storage abstraction. Owns the
generalized polymorphic attachment plumbing (issue #55) — any module
that needs to attach a Document to one of its rows talks to this
module via `AttachmentService` + the `attachment_registry`.

## Public API

Routes mounted at `/api/v1/media/`.

### Documents (administrative — PDFs, consents, …)

- `POST   /patients/{id}/documents`        — multipart upload; `media.documents.write`
- `GET    /patients/{id}/documents`        — list, filter `document_type`, `media_kind`
- `GET    /documents/{id}`                 — metadata
- `GET    /documents/{id}/download?variant=full|medium|thumb`
- `PUT    /documents/{id}`                 — patch metadata
- `DELETE /documents/{id}`                 — soft-archive

### Photos / X-rays (taxonomy-aware)

- `POST   /patients/{id}/photos`           — multipart with `media_kind`, `media_category`,
  `media_subtype`, `captured_at?`, `paired_document_id?`. Generates
  `thumb` + `medium` derivatives via Pillow and reads EXIF for
  `captured_at` when omitted.
- `GET    /patients/{id}/photos`           — gallery list with filters
  (`media_kind`, `media_category`, `media_subtype`, `captured_from`,
  `captured_to`, `pair_status`).
- `PATCH  /documents/{id}/photo-metadata`  — edit category / subtype /
  capture date / tags / pairing.
- `POST   /documents/{id}/pair/{other_id}` — set bidirectional
  before/after pairing (same patient enforced).
- `DELETE /documents/{id}/pair`            — remove pairing.

### Polymorphic attachments

- `POST   /attachments`                    — `{document_id, owner_type,
  owner_id, display_order?}`. Owner resolved via the registry.
- `DELETE /attachments/{id}`               — unlink (Document stays).
- `GET    /attachments?owner_type&owner_id` — list for an owner.

## Dependencies

`manifest.depends = ["patients"]`. No outbound coupling to consumer
modules — they register their owner_types into us at import time
through `attachment_registry`.

## Permissions

- `media.documents.read` / `media.documents.write` — file CRUD.
- `media.attachments.read` / `media.attachments.write` — link CRUD.

## Events emitted

- `document.uploaded` — every upload. Photos / X-rays are skipped here
  so the timeline doesn't show a duplicate row alongside `photo.uploaded`.
- `document.deleted`
- `document.archived`
- `media.photo_uploaded` — photo-aware variant fired alongside
  `document.uploaded` whenever `media_kind ∈ {photo, xray}`.
- `media.attachment_linked` / `media.attachment_unlinked`
- `media.pair_created` / `media.pair_removed`

## Events consumed

- `patient.archived` → cascade soft-archive of associated documents.
- `patient.restored` → reverse the cascade (documents back to active).

## Lifecycle

- `removable=False`. Treatment_plan, clinical_notes, patient_timeline
  depend on this module.

## Gotchas

- **Storage backend is pluggable** (`STORAGE_BACKEND` env var).
  Currently `local`. The future `media_s3` module extends
  `StorageBackend` without API changes.
- **Thumbnails** are precomputed on upload (`thumbnails.py`) at two
  sizes (`{path}.thumb.jpg`, `{path}.medium.jpg`). Originals stay
  untouched. The download endpoint accepts a `variant` query param.
- **EXIF capture timestamp** is extracted server-side via Pillow in
  `exif.py`. Manual override via `PATCH /documents/{id}/photo-metadata`.
- **MIME validation is mandatory** — see `validation.py`. The photo
  path extends the base allowlist with `image/heic|heif|webp|gif` so
  iOS uploads work without per-clinic config changes.
- **Files must be scoped by `clinic_id`** in the storage layout.
- **`media_attachments.owner_type` has no CHECK constraint** by design
  — see ADR 0007. Validation lives in `attachment_registry`.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0007-polymorphic-attachment-registry.md`
- `docs/adr/0008-photo-storage-retention-stub.md`

## CHANGELOG

See `./CHANGELOG.md`.
