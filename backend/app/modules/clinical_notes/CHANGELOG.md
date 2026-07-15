# Changelog — clinical_notes

## Unreleased

- i18n: correct French terminology in `fr.json` (Diagnostic).

- i18n: add French locale (`fr.json`); add French translations to seed
  data; add `body_i18n_key` to template responses so template bodies
  resolve in the active locale. Labels now resolve via
  `es → en → fr` catalog-name fallback (still falling back to
  `treatment.clinical_type` when no catalog item). Date formatting in
  NoteCard, PlanNotesTimeline, and PatientClinicalNotesByPlan uses
  locale-aware `toLocaleString(locale)`.

- feat(appointment-owner): add ``owner_type='appointment'`` with two
  new ``note_type`` values (``appointment_clinical`` +
  ``appointment_administrative``) so notes can attach to a
  ``agenda.Appointment``. Matrix CHECK extended (``cn_0003``); media
  owner registry resolves ``appointment → patient`` so adjuntos
  surface in the patient gallery. Two new events
  (``CLINICAL_NOTE_APPOINTMENT_CLINICAL_CREATED`` /
  ``CLINICAL_NOTE_APPOINTMENT_ADMINISTRATIVE_CREATED``) follow the
  existing ``clinical_notes.<note_type>_created`` naming so
  ``patient_timeline`` picks them up via its string-derived dispatch.
  Frontend: new ``AppointmentNotesPanel`` mounted on the
  ``appointment.detail.notes`` slot (agenda hosts; no cross-import).
- feat(ux): hovering or keyboard-focusing a note in ``DiagnosisNotesSidebar`` or
  ``PlanNotesTimeline`` now pulses the matching tooth on the odontogram, mirroring
  the existing hover behaviour of the per-tooth treatment list. ``DiagnosisNotesSidebar``
  resolves the tooth via two new optional ``ctx`` props (``treatmentsToothById`` +
  ``onTeethHover``) so the module stays decoupled from odontogram. ``PlanNotesTimeline``
  emits ``item-hover`` (matching ``PlanTreatmentList``); ``PlanDetailView`` wires it
  into the existing ``hoveredItemId`` highlight pipeline. Notes with no tooth
  (plan-level, administrative without ``tooth_number``) silently no-op — no ghost
  pulse.
- feat(timeline): surface author (avatar + name) on every entry in the plan notes timeline. ``ClinicalNoteEntry`` now carries an ``author: AuthorBrief | None`` (notes: from ``ClinicalNote.author``; visits: from ``Appointment.professional``). ``PlanNotesTimeline.vue`` renders the author header so the dentist can tell who wrote each note at a glance.
- refactor(perms): migrate hardcoded ``can('clinical_notes.notes.{read,write}')`` strings in ``TreatmentNoteButton`` / ``DiagnosisNotesSidebar`` / ``PlanNotesTimeline`` / ``RecentNotesFeed`` to ``PERMISSIONS.clinicalNotes.*``.
- fix(isolation): declare ``agenda`` in ``manifest.depends`` — the
  service already imported ``Appointment`` / ``AppointmentTreatment``
  to surface visit-level notes. The dependency was real, just
  undeclared. ``KNOWN_VIOLATIONS`` allowlist trimmed accordingly.

### Changed

- **0.2.0 (issue #55)** — Polymorphic attachments delegated to `media`:
  the legacy `clinical_note_attachments` table is dropped (migration
  `cn_0002`, depends on `med_0002`); the model is removed and the
  service/routes now proxy to `media.AttachmentService`. New
  `owner_resolvers.py` registers `patient`, `treatment`, `plan` and
  `clinical_note` owner_types with `media.attachment_registry` at
  module import time. `NoteService.create`
  links each `attachment_document_id` twice (once to the note's owner
  for gallery surfacing, once to `clinical_note` for note-scoped
  rendering).
- `DiagnosisNotesSidebar` now uses cursor pagination (`limit=20`,
  `before` timestamp) with a "Cargar más" button, mirroring
  `RecentNotesFeed`. Previously fetched a hard-coded `limit=30` once
  and stopped.

### Fixed

- `DiagnosisNotesSidebar` no longer highlights every note without a
  tooth on load. The previous `selectedTooth === tooth_number` check
  matched `null === null` when no tooth was selected, painting a blue
  `ring-2 ring-primary` around all administrative / non-tooth-bound
  diagnosis notes until a tooth was clicked.

### Added

- Demo seed (`seed.py::seed_clinical_notes_demo`) wired into
  `scripts/seed_demo.py` step 7. Creates administrative + diagnosis
  notes per patient (diagnosis tooth-pinned where odontogram has data),
  `treatment_plan` notes on ~2/3 of plans and `treatment` notes on
  every other performed treatment, with author rotation between dentist
  and hygienist and time-staggered `created_at`. Inserts rows directly
  without firing events to keep `patient_timeline` re-derivation clean.
- New module owning the polymorphic `clinical_notes` and
  `clinical_note_attachments` tables (extracted from `treatment_plan`).
- `note_type` discriminator: `administrative`, `diagnosis`, `treatment`,
  `treatment_plan`.
- `tooth_number` column on `clinical_notes` for diagnosis notes
  optionally tied to a tooth.
- New owner type `treatment` — notes attach directly to the underlying
  `treatments.id` so they travel with the Treatment from diagnosis →
  plan → completion.
- Endpoints: `/notes`, `/attachments`, `/patients/{id}/recent`,
  `/patients/{id}/by-plan`, `/treatment-plans/{id}/merged`,
  `/note-templates`.
- Events: `clinical_notes.{administrative,diagnosis,treatment,plan}_created`.
- Migration `cn_0001` extends the legacy `clinical_notes` /
  `clinical_note_attachments` tables in place; backfills `note_type`
  and remaps `plan_item` notes onto the underlying `treatment` row.

### Changed

- Existing `treatment_plan.notes.*` permissions are replaced by
  `clinical_notes.notes.*`. The completion modal and per-row note UI
  in `treatment_plan` now call this module's API.

### Removed

- Notes-related endpoints, services and models from `treatment_plan`.
- `DiagnosisNotesSidebar` no longer exposes Tratamiento / Administrativas
  tabs. The composer is diagnosis-only (treatment notes belong on the
  treatment-plan UI; administrative notes are written from the patient
  Summary feed), but the listing shows **every** note type colour-coded
  via `NoteCard` so the dentist sees full context. The sidebar still
  receives `sessionTreatmentIds` in ctx but ignores it.
- `PlanNotesTimeline` redesigned: source-coloured left border on each
  card (plan = secondary, treatment = success, visit = primary), source
  icon + treatment name in the card header, and a Todas / Plan /
  Tratamiento / Visita filter row matching the patient Summary feed UX.
  The merged endpoint already returned plan + treatment + visit notes;
  the new visual makes that obvious at a glance.
