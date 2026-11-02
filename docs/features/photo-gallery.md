# Patient photo gallery + generalized attachments

> Issue #55 · ships in DentalPin 2026-05 · backend module `media` 0.2.0

## Why

Three pain points lined up around the same backend primitive:

1. Clinics need a **photo-first UX** for clinical imagery (intraoral,
   extraoral, X-rays, before/after) — not a PDF list with a small
   embedded image.
2. The note composer has no way to **attach a photo while writing the
   note**. Today the dentist uploads a document elsewhere and then
   writes prose referring to "see the photo I uploaded".
3. Each module that wanted to attach a Document to one of its rows
   (notes, plan items, visits) reimplemented the polymorphic join
   table. Adding a fourth module would mean a fourth copy.

We solve all three together because they share the same backend
plumbing: a Document with media-aware columns and a generic
attachment table.

## What

### Patient detail page

A new **"Galería"** tab next to "Administración" / "Cronología" with
the photo gallery for that patient.

- Square-thumbnail grid (responsive: 2 cols on phone → 6 on desktop).
- Category rail: `Todas | Intraoral | Extraoral | Radiografías |
  Antes/Después | Otras`. Subtype chips appear below when a category
  is selected.
- Lightbox: swipe (touch), keyboard navigation (`← / → / Esc`),
  metadata footer (kind / category / subtype / tags), zoom on the
  medium-size derivative.
- Upload modal: single-file picker + drag-drop, kind / category /
  subtype / capture-date selectors. EXIF capture date filled in
  server-side from Pillow.
- Before/after pairing: API exists; UI surfaces the link badge on a
  paired card. The split-slider comparison view is ship-1.5 (a
  dedicated component will replace the inline lightbox view once UX
  feedback narrows the interaction).

### Note composer

`<NoteComposer>` (used by Summary feed, diagnosis sidebar, treatment
row popover, plan timeline) gets a new optional `patient-id` prop.
When present:

- Adds a "Adjuntar foto" button next to Save / Cancel.
- Each picked file is uploaded immediately as a clinical photo
  (`media_kind=photo`, `media_category=clinical`,
  `media_subtype=reference`) so the dentist can see the thumbnail
  before saving.
- On submit, the resulting `document_id`s are sent in
  `attachment_document_ids`. The backend creates two link rows: one to
  the note's owner (so the document shows up in the plan / treatment
  gallery) and one to `clinical_note` (so the note's renderer can
  fetch its attachments).

### Visit panel (agenda)

`<VisitNotePanel>` mounts an `<AttachmentThumbStrip>` bound to
`owner_type='appointment_treatment'` so radiographs uploaded directly
on the visit kanban surface inline.

### Documents tab

The original `<DocumentGallery>` stays under Administración → Documents
and is restricted to non-photo documents (`media_kind=document`).
PDFs, consents, insurance, reports continue to live there unchanged.

## How (backend)

| Layer | Where |
|---|---|
| Data model | `documents` gains `media_kind`, `media_category`, `media_subtype`, `captured_at`, `paired_document_id`, `tags`. New `media_attachments` table is the polymorphic owner store. |
| Migrations | `med_0002` (schema), `cn_0002` (drop `clinical_note_attachments`, backfill), `tp_0004` (drop `treatment_media`, backfill). All in one PR. |
| Services | `DocumentService.create_document` accepts photo metadata, generates thumbnails (Pillow), reads EXIF. `PhotoService` handles gallery filters / pairing. `AttachmentService` is the polymorphic link CRUD. |
| Routes | `/api/v1/media/patients/{id}/photos`, `/api/v1/media/documents/{id}/photo-metadata`, `/api/v1/media/attachments`, plus pairing endpoints under `/documents/{id}/pair/...`. |
| Owner registry | `media/attachment_registry.py` — process-global. Consumer modules (`clinical_notes`, `treatment_plan`) register via their `__init__.py`. See ADR 0007. |
| Events | `media.photo_uploaded`, `media.attachment_linked/unlinked`, `media.pair_created/removed`. |

## How (frontend)

| Component | Path | Purpose |
|---|---|---|
| `PhotoGallery.vue` | `media/frontend/components/media/` | Grid + category rail + upload modal + lightbox |
| `PhotoCard.vue` | same | Square thumbnail with hover overlay + pair badge |
| `PhotoLightbox.vue` | same | Fullscreen viewer (touch/keyboard) |
| `PhotoUpload.vue` | same | Single-file form with full taxonomy picker |
| `AttachmentThumbStrip.vue` | same | Reusable compact thumb strip used by note composer / visit panel |
| `usePhotos` | `media/frontend/composables/` | Wraps photo endpoints |
| `useAttachments` | same | Wraps generic attachment endpoints |

## Out of scope (follow-ups)

- Native mobile camera capture (`<input capture="environment">`).
- Tenant-scoped S3 prefix wrapper and presigned download URLs (the S3
  backend itself shipped inside `media`, T6).
- Active retention / lifecycle enforcement (see ADR 0008).
- AI photo analysis (caries detection, etc.).
- Per-photo access control beyond the current module-level RBAC.

## Ship checklist

- Backend tests: `test_media_photos.py`, `test_media_attachments.py`.
- Smoke flow: upload a photo on a demo patient, see it in the new
  Galería tab, open the lightbox, pair before/after, attach a photo
  while creating an administrative note from the Summary feed.
- Mobile dev-tools sanity (375px): grid drops to 2 columns, lightbox
  swipe works, drop-zone falls back to the native file picker.
