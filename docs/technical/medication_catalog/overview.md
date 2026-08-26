# medication_catalog — overview

Clinic-wide medication list: name, dose, unit, pharmaceutical form and
prescribable/active status. CRUD lives under **Settings → Clinical**
(`/settings/clinical/medications`, same area as the treatment
catalogue) — there is no main-sidebar entry.

Seeded with a **56-item dental medication list** (antibiotics,
analgesics, local anaesthetics, emergency kit, corticosteroids,
antifungals/antivirals, oral care, GI/allergy tail). The seeder is
idempotent — it runs on `clinic.created` (own session), on demand via
`POST /medication_catalog/seed`, and can be re-run after imports
without duplicating anything.

## Integrity guarantees

- Names are unique per clinic **case-insensitively**. The service
  answers 409 on duplicate create/rename (mirroring
  medical_reference); a functional unique index over
  `(clinic_id, lower(btrim(name)))` closes the concurrent-create race
  at the database (the inventory #153 lesson: guard invariants in SQL).
  The service's normalisation matches that index key exactly, so a
  duplicate is always a 409 and never a raw constraint error.
- Inactive items stay in the list for history; nothing is silently
  mutated.

## Data source for prescriptions

The document-generation module reads this catalog cross-module under
ADR 0002 to render the medication block of prescriptions, which is why
`form` is constrained to a fixed set (`MEDICATION_FORMS`) rather than
free text.

## Install policy

Optional module: `depends: []`, `auto_install=False`, `removable=True`.
Default roles: `admin` manages, `dentist` reads.
