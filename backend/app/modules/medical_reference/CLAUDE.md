# medical_reference module

Clinic-managed lookup lists for allergies, medications, systemic
diseases, and surgeries — the source of the searchable dropdowns behind
`patients_clinical`'s medical-history inputs — plus active
interaction/contraindication flagging against a patient's *currently
recorded* medications and diseases.

## What it does

Four flat reference lists (allergy, medication, disease, surgery), each
clinic-managed (create/search/update/deactivate — deactivate is soft,
same reasoning as `contacts`: existing patient records that reference an
item by id shouldn't break if it's later retired). Two relationship
tables on top: `ReferenceInteraction` (medication × medication) and
`ReferenceContraindication` (disease × medication), each carrying a
`risk_note`.

`get_patient_flags` cross-references a patient's recorded
`patients_clinical.Medication`/`SystemicDisease` rows (matched by
`reference_id` — free-text-only legacy entries aren't fuzzy-matched, so
they're silently excluded) against the interaction/contraindication
tables to surface active warnings. This is the one place the module
reads another module's data directly.

## Tenancy

Every reference row has its own `clinic_id`, and every lookup —
including the direct-by-id ones (`get`, `get_interaction`,
`get_contraindication`) that back every update/deactivate endpoint — is
filtered on it. Confirmed by
`tests/modules/medical_reference/test_tenant_isolation.py`, which checks
cross-clinic access is blocked for all three lookup paths, not just the
list/search ones.

## Permissions

`dentist` has `read`+`write` here — clinical judgment calls (recording a
new allergy on the fly, adjusting a risk note) are a dentist's to make,
same precedent already set by `patients_clinical`'s own
`medical.read`/`medical.write` split. `hygienist`/`assistant`/
`receptionist` are read-only.

## Dependencies

`manifest.depends = ["patients_clinical", "patients"]`. `patients_clinical`
is the real functional dependency (`get_patient_flags` reads its
`Medication`/`SystemicDisease` models). `patients` is declared because
`router.py` imports `patients.service.PatientService` directly — even
though `patients_clinical` itself depends on `patients` transitively,
CLAUDE.md's rule is about direct imports, so it needs its own explicit
entry here too.

`patients_clinical` links back to this module only loosely (a plain
nullable UUID `reference_id`, no DB-level FK) — so it keeps working
standalone if `medical_reference` is ever uninstalled. The dependency
only goes one direction.

## Lifecycle

- `installable=True`, `auto_install=False` (optional modules ship
  manual-install here — activated from the admin UI), `removable=True`.
- Own Alembic branch (`medical_reference`), rooted independently on core
  `"0001"`. No `depends_on` needed — every FK here is either core
  (`clinics.id`) or within this module's own branch.

## patients_clinical integration

The searchable comboboxes and the per-patient warning flags are wired via
**slots**, never direct component imports:

- `patients_clinical`'s `MedicalHistoryForm.vue` renders a named slot for
  each history-table name input
  (`patients_clinical.medical_history.{allergy|medication|disease|surgery}_name`)
  with the plain `UInput` as fallback when nothing is registered.
- This module's `frontend/plugins/settings.client.ts` registers its
  adapter component into those slots; when the module isn't installed the
  form silently falls back to free-text inputs (and those entries simply
  have no `reference_id`, so they're excluded from flag matching).
- Flags surface by registering a chip component into the existing
  `patient.header.alerts` slot owned by `patients`/`patients_clinical`
  (same pattern they themselves use) — their alert banner is never edited.
- The chips **subscribe to the host data bus** on the
  `patients_clinical` namespace (ADR 0021): after any medical-history
  save, the warning chips refetch immediately — clinical safety data
  must not go stale until a page reload.

## CHANGELOG

See `./CHANGELOG.md`.
