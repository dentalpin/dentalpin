# Changelog — patients_clinical module

## Unreleased

- fix(data): deletes are now soft-deletes (audit DATA-01). `delete_*`
  sets `status = "archived"` instead of hard-deleting; lists show only
  active rows, gets still return archived rows for history, contact
  upserts revive, and the bulk replace archives the superseded set.
  New `status` column (`pc_0003`, existing rows backfill `active`).

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

- fix(#274): `saveMedicalHistory()` publishes a `patients_clinical` tick
  on the host data bus (ADR 0021) after a successful PUT, and
  `usePatientAlerts` subscribes to it. The header alert chips no longer
  keep showing a deleted allergy — or hide a just-added critical one —
  until a full page reload; any other module rendering into the patient
  header refreshes off the same tick.
- Added nullable `reference_id` UUID to `Allergy`, `Medication`,
  `SystemicDisease`, and `SurgicalHistory` (migration `pc_0002`),
  exposed in the Create/Update/Response schemas. It is a loose link —
  a plain UUID column with **no DB-level FK** — to rows in the optional
  `medical_reference` module's lookup lists, set by its searchable
  comboboxes when they're registered into this form's name-input slots.
  The module stays fully standalone if `medical_reference` is not
  installed or is uninstalled: entries created from plain free-text
  inputs simply keep `reference_id = null`.
- `MedicalHistoryForm.vue` now exposes an extension point per history
  name input (`patients_clinical.medical_history.{allergy,medication,
  disease,surgery}_name`) rendering the existing plain input as
  fallback. This module does not import any other module's component —
  consumers register into the slots.
- fix(#184): type-check clean — `UAccordion :ui.item` is a class string in Nuxt UI v4 (the border/margin classes were not applied), `getSeverityColor()` returns `UiColor`, allergy rows key by index (entries have no `id`).
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast in ``useMedicalHistory`` now that ``useApi`` accepts ``object`` payloads.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Normalized medical history, allergies, medications, emergency contacts.
- `patient.medical_updated` event for the timeline.
- Role-scoped permissions: hygienists read-only on medical, write on emergency.
