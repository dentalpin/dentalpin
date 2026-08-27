# Changelog — medical_reference module

## Unreleased

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.
- fix(#274): the patient warning chips subscribe to the host data bus on
  the `patients_clinical` namespace (ADR 0021) and refetch after every
  medical-history save, instead of going stale until a page reload. The
  chips are cleared only when the header switches patient, so a refetch
  never blinks the warning out and back in.
- feat(#131): German (de) locale for the module's frontend layer.
- fix: the medical-history name combobox now follows the host form's
  reset after adding an entry (the slot adapter mirrored `ctx.value`
  only at mount, so the field kept showing the previous selection).
- fix: renaming a reference item onto another row's name returns 409
  (was a raw unique-constraint 500); renaming to a case variant of its
  own name stays allowed.
- chore: dropped the leftover `apci` settings search keyword.

## 0.4.0 — patients_clinical integration

- `patients_clinical` gained a nullable `reference_id` UUID on its four
  history tables (own migration, no DB-level FK), exposed in its
  schemas; every lookup-list entry created from the searchable inputs is
  now linked to the patient record that used it.
- `MedicalHistoryForm.vue` exposes a slot per name input
  (`patients_clinical.medical_history.*_name`) with the plain input as
  fallback; this module registers its searchable combobox into the slots
  from its own plugin — dependency direction preserved (no core-module →
  community-component imports).
- Per-patient interaction/contraindication warnings surface in the
  patient header via the existing `patient.header.alerts` slot.
- End-to-end regression test for `GET /patients/{id}/flags`.
- Tenant isolation on every direct-by-id lookup (`clinic_id` filter on
  `get`, `get_interaction`, `get_contraindication`), covered by
  `test_tenant_isolation.py`.
- `depends` declares both `patients_clinical` and `patients`;
  `auto_install=False`; admin-only write except dentist (clinical
  judgment calls), other roles read-only.
- Settings UI for managing all six lists (categories, interactions,
  contraindications) under the module settings registry.

## 0.3.0

- Interaction and contraindication tables, plus `get_patient_flags` for
  active per-patient warnings.

## 0.2.0

- Surgery reference list.

## 0.1.0

- Initial schema: allergy, medication, disease reference lists.

