---
module: medication_catalog
screen: clinical-medications
route: /settings/clinical/medications
related_endpoints:
  - GET /api/v1/medication_catalog
  - POST /api/v1/medication_catalog
  - PATCH /api/v1/medication_catalog/{id}
  - DELETE /api/v1/medication_catalog/{id}
  - POST /api/v1/medication_catalog/seed
related_permissions:
  - medication_catalog.read
  - medication_catalog.write
related_paths:
  - backend/app/modules/medication_catalog/frontend/components/settings/MedicationCatalogSettingsPage.vue
last_verified_commit: 615ad10
---

# Medication catalog

Found under **Settings → Clinical**. The list is ordered
alphabetically and paginated (20 per page).

## What you can do

- **Search** by name (live, debounced).
- **Filter** by pharmaceutical form or show active items only.
- **Add / edit** — name, dose, unit, form, "Rx required" and active
  status. Names are unique per clinic regardless of case: a duplicate
  shows an error instead of creating two entries.
- **Delete** with confirmation. Already-issued prescriptions keep their
  own copy of the data.
- **Load starter set** — adds the 56-item dental medication list.
  Running it twice never duplicates anything.

Inactive medications stay in the list (greyed status) so history and
prescriptions remain meaningful.

## Who can use it

Admins manage the catalog; dentists have read access. Other roles need
to be granted `medication_catalog.read` / `.write` explicitly from the
module admin UI.
