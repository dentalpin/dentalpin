---
module: medical_reference
last_verified_commit: 829bdd25
---

# medical_reference — overview

Clinic-managed lookup lists for allergies, medications, systemic
diseases and surgeries, plus known medication–medication interactions
and disease–medication contraindications. The lists back the searchable
comboboxes on the patient medical-history form; the interaction tables
power active per-patient warnings.

## What it does

- Four flat reference lists (allergy / medication / disease / surgery),
  each clinic-managed: search, create, update, deactivate (soft delete —
  items already used on patient records must keep existing).
- Two relationship tables on top: `ReferenceInteraction`
  (medication × medication) and `ReferenceContraindication`
  (disease × medication), each with a `risk_note`. Pairs are stored in a
  canonical order (`medication_a_id < medication_b_id`, string-sorted)
  so the unique constraint reliably blocks duplicates regardless of the
  order they were entered in. Adding a pair (or a list name) that
  matches a deactivated row reactivates that row — for pairs with the
  new `risk_note` — instead of answering 409; an active duplicate still
  answers 409 (#963, #1236).
- `GET /patients/{patient_id}/flags` cross-references a patient's
  *currently recorded* medications and diseases against those pairs.

## patients_clinical integration

The dependency points one way only:

- **Backend** — `patients_clinical` carries a nullable `reference_id`
  UUID on its four history tables (its own migration `pc_0002`). It is a
  loose link: no DB-level FK, so `patients_clinical` stays fully
  standalone when this optional module is not installed or is
  uninstalled.
- **Frontend** — `MedicalHistoryForm.vue` exposes one slot per name
  input (`patients_clinical.medical_history.{allergy|medication|
  disease|surgery}_name`) with the plain text input as fallback. This
  module registers its combobox into those slots from its own plugin;
  nothing imports across modules. Flags surface by registering a chip
  component into the existing `patient.header.alerts` slot — the host
  banner is never edited.
- Entries created from the fallback free-text inputs have
  `reference_id = null`; they are excluded from flag matching rather
  than fuzzy-matched (see `MedicalReferenceService.get_patient_flags`).

## Tenancy

Every reference row has its own `clinic_id` and every lookup — including
the direct-by-id ones backing update/deactivate — filters on it
(regression-tested in `test_tenant_isolation.py`). The flags endpoint
verifies the patient belongs to the caller's clinic before reading its
history rows, which are themselves filtered by `patient_id`.

## Lifecycle

- Optional community module: `installable=True`, `auto_install=False`
  (activated from the admin UI), `removable=True`.
- Own Alembic branch (`medical_reference`), rooted independently on core
  `"0001"`, no `depends_on`.
