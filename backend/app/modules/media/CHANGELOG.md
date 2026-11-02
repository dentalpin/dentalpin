# Changelog — media module

## Unreleased

- feat: S3-compatible object storage backend (`storage/s3.py`) behind the
  existing `StorageBackend` seam, selected with `STORAGE_BACKEND=s3` (T6).
  `STORAGE_S3_BUCKET` is required in that mode; `STORAGE_S3_REGION` /
  `STORAGE_S3_ENDPOINT_URL` target MinIO/Wasabi/R2 and empty credentials
  fall back to the standard AWS chain. The factory refuses `s3` without a
  bucket instead of failing on the first upload (the unknown-backend-name
  ValueError is pre-existing and now test-covered); prod/coolify composes
  interpolate `STORAGE_BACKEND` with a `local` default so the template's
  opt-in flips the real switch. SDK calls run via `asyncio.to_thread` so
  the sync boto3 client never blocks the event loop. Keys are forwarded
  in all three deployment compose files and documented in the shipped
  `.env` templates; boto3 added to `pyproject.toml` (uv.lock updated).
  11 tests cover put/get/head/delete semantics, the full NOT_FOUND code
  set -> FileNotFoundError mapping, unexpected-error passthrough,
  constructor wiring and the factory guards.

- fix(#743): emptying a document's description in the edit modal kept the
  old text. The modal sent `|| undefined` (key dropped) and
  `update_document` skipped every `None`. The modal now sends `null` and
  the service stores it for `description` (`_CLEARABLE_DOCUMENT_FIELDS`);
  other `None` / omitted fields are still left untouched.
- fix(#730): the patient document/photo gallery pager never changed page. It bound `v-model` / `:page-count`; Nuxt UI v4 needs `v-model:page` / `:items-per-page`, so documents after the first 12 were unreachable.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- docs(#711): the events doc said the module publishes nothing; it
  publishes seven events, now tabled. CLAUDE.md also put the
  photo/X-ray de-duplication in the publisher — it lives in
  `patient_timeline`'s handler, `document.uploaded` fires for every upload
  — and listed `document.archived` as emitted while nothing publishes it.
- fix(#697): the upload controls' "Change" button and the "Optional"
  field hint, and the photo/document/attachment toasts, existed in no
  locale file — the hardcoded default message rendered for every
  language (`Cambiar`, `Opcional`, "Error loading photos"). The keys
  (`actions.change`, `common.optional`, `documents.viewError`,
  `attachments.linkError`, `photoGallery.{fetchError,uploadError,uploadSuccess}`)
  are now in all 12 host locales and the defaults are dropped.

- fix(#631): the document card's view tooltip used `common.view`, which
  exists in no locale file, so it rendered the key string; it now reuses
  `common.viewDetails`, matching the button's own `aria-label`. The
  before/after pairing toast uses the existing `photoGallery.pair.paired`
  instead of a hardcoded English default, so it is translated.
- feat(#657): owns the `media` GDPR erasure coverage scope
  (`get_erasure_contributors()`). Imaging, clinical photos and uploaded
  patient files are retained as care records (Art. 17(3)(c)/(h)). One of
  the three scopes that replaced `gdpr`'s hardcoded `clinical` row.

- fix: the download `Content-Disposition` filename is sanitized (quotes,
  backslashes and control characters stripped, `document` fallback) — the
  stored name comes from the uploader and must never reach the header
  verbatim.
- fix: gallery and photo-upload preview render a generic placeholder for
  non-image files (e.g. DICOM) instead of a broken `<img>`.
- fix: `application/octet-stream` uploads pass validation when the
  filename ends in `.dcm` (browsers sniff DICOM that way) — the
  viewer's `DICM` magic check, not the mime, decides radiology.
  Anything else stays rejected.
- fix(events): `create_document` publishes `document.uploaded` /
  `media.photo_uploaded` transactionally (`db=db`, ADR 0019) — any
  subscriber declaring a `db` handler (e.g. imaging_viewer's DICOM
  auto-index) previously crashed every photo/X-ray upload with
  RuntimeError; the index now shares the upload's session.
- fix(#452): the document list, delete and update go through `useApi` (401 → refresh → retry, CSRF, SSR cookies); the upload stays on `$fetch` for FormData/progress and retries once after `auth.refresh()` on 401, ending the session when the refresh fails.

- fix(#431 review round 3): `unarchive_patient_documents` docstring
  says every archived document is restored (matches the query).
- fix(#431 review): `patient.restored` handler reverses the document
  archive cascade (transactional).
- feat(i18n): the frontend layer's directional spacing, borders, text alignment and inset positioning now resolve against the document direction (physical→logical CSS utilities, Arabic RTL support).

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

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
