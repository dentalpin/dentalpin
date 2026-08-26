---
module: medication_catalog
last_verified_commit: 76b1273a
---

# Medication catalog

Clinic-wide medication list under **Settings → Clinical**: name, dose,
unit, pharmaceutical form and prescribable/active status. Ships with an
idempotent 56-item dental starter set; admins manage it, dentists read
it. It is the data source for prescriptions (document generation).

## Screens

- [Medication catalog](./screens/clinical-medications.md): search,
  form/status filters, add/edit/delete with duplicate-name protection,
  starter-set loader.
