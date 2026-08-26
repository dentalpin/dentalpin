# Changelog — media module

## Unreleased

- fix(#127): every icon-only button in the module's frontend has an i18n-sourced `aria-label` (screen readers announced them as just "button").

- fix(#184): type-check clean — drop the `onRequest` hook that cast ofetch's `Headers` to delete `Content-Type` (ofetch already leaves it unset for `FormData`).
- fix(#183): `patient.archived` cascade is transactional (ADR 0019) — the documents are archived with the patient, and no longer stay archived when the request rolls back. Covered end-to-end now that it shares the publisher's session.
- fix(events): repair the `patient.archived` cascade, which had never
  run (audit event-bus #1, #95). The handler signature took
  `(self, db, data)` but the bus calls `handler(data)`, raising
  `TypeError` on every archive; it also read `data["clinic_id"]` while
  the publisher sent only `patient_id`. Handler now takes `(data)`,
  opens its own session + commits (publish-before-commit), and guards a
  missing payload. Depends on the patients publisher now emitting
  `clinic_id`.

- perf(lists): drop the ``select_from(query.subquery())`` count
  anti-pattern in ``DocumentService.list_documents`` and
  ``PhotoService.list_photos``; both lists now count via a direct
  ``COUNT(Document.id)`` over the same filter set.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- **0.2.0 (issue #55)** — Photo gallery + generalized polymorphic
  attachments (2026-05-02):
  - `Document` gains `media_kind`, `media_category`, `media_subtype`,
    `captured_at`, `paired_document_id`, `tags` columns. New
    `media_attachments` table replaces both `clinical_note_attachments`
    and `treatment_media`.
  - New endpoints: photo upload (`POST /patients/{id}/photos`) with
    EXIF + Pillow thumbnail generation, gallery list, before/after
    pairing, `/attachments` polymorphic CRUD.
  - Owner-type registry in `attachment_registry.py` — clinical_notes
    and treatment_plan register their owner_types at import time
    (ADR 0007).
  - New permissions `media.attachments.read` / `media.attachments.write`.
  - New events `media.photo_uploaded`, `media.attachment_linked`,
    `media.attachment_unlinked`, `media.pair_created`,
    `media.pair_removed`.
  - Pillow added as a backend dependency.
  - HEIC / HEIF / WebP / GIF added to the photo MIME allowlist.

## 0.1.0 — initial

- Local storage backend with MIME and size validation.
- `document.uploaded`, `document.deleted` events.
- Subscribes to `patient.archived` for cascade.
