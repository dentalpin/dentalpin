---
module: catalog
screen: catalog
route: /settings/catalog
related_endpoints:
  - DELETE /api/v1/catalog/categories/{category_id}
  - DELETE /api/v1/catalog/items/{item_id}
  - DELETE /api/v1/catalog/vat-types/{vat_type_id}
  - GET /api/v1/catalog/categories
  - GET /api/v1/catalog/categories/{category_id}
  - GET /api/v1/catalog/items
  - GET /api/v1/catalog/items/popular
  - GET /api/v1/catalog/items/search
  - GET /api/v1/catalog/items/{item_id}
  - GET /api/v1/catalog/odontogram-treatments
  - GET /api/v1/catalog/odontogram-treatments/by-category
  - GET /api/v1/catalog/vat-types
  - GET /api/v1/catalog/vat-types/default
  - GET /api/v1/catalog/vat-types/{vat_type_id}
  - POST /api/v1/catalog/categories
  - POST /api/v1/catalog/items
  - POST /api/v1/catalog/seed
  - POST /api/v1/catalog/vat-types
  - PUT /api/v1/catalog/categories/{category_id}
  - PUT /api/v1/catalog/items/{item_id}
  - PUT /api/v1/catalog/vat-types/{vat_type_id}
related_permissions:
  - catalog.read
  - catalog.write
  - catalog.admin
related_paths:
  - backend/app/modules/catalog/frontend/pages/settings/catalog/index.vue
  - backend/app/modules/catalog/frontend/components/catalog/CatalogCategoriesModal.vue
last_verified_commit: 71402014
---

# /settings/catalog

Treatment catalog: codes, prices, VAT, duration and grouping by category.
It is the price source for budgets, plans and invoices.

## Permissions

- `catalog.read` — browse the catalog (every role).
- `catalog.write` — create, edit and deactivate treatments.
- `catalog.admin` — manage categories and load the default catalog.

## What this screen does

- **Search and filter** treatments by text or category; the grouped view
  collapses/expands per category.
- **New treatment** — the modal requires code, name and **category**;
  without categories nothing can be saved.
- **Categories** (header button, `catalog.admin` only) — create, rename,
  reorder and deactivate/reactivate categories. System (seeded) categories
  are locked: shown with a padlock, and the server rejects edits/deletes.
- **System treatments** (*System* badge) — price, cost, VAT, names, duration,
  sessions and active status can be edited. Code, category, pricing strategy
  and scope are locked, and they cannot be deleted.
- **Load default catalog** — shown in the empty state (no treatments, no
  filters) to `catalog.admin`. Adds VAT types for the clinic country, the
  categories and the reference treatments (prices at 0 when the currency is
  not EUR). Idempotent: only missing rows are created. This is the repair
  path for installs created before automatic seeding existed or where it
  failed; the dashboard "Getting started" card links here when it detects an
  empty catalog.
- On narrow screens, the treatment pricing fields wrap into two columns;
  wider screens show up to five columns.
