---
module: inventory
screen: index
route: /inventory
related_endpoints:
  - GET /api/v1/inventory/
  - POST /api/v1/inventory/
  - GET /api/v1/inventory/{inventory_item_id}
  - PATCH /api/v1/inventory/{inventory_item_id}
  - DELETE /api/v1/inventory/{inventory_item_id}
  - POST /api/v1/inventory/{inventory_item_id}/adjust-stock
  - GET /api/v1/inventory/low-stock
  - GET /api/v1/inventory/stats/dashboard
  - GET /api/v1/inventory/categories
  - POST /api/v1/inventory/categories
related_permissions:
  - inventory.read
  - inventory.write
  - inventory.delete
related_paths:
  - backend/app/modules/inventory/frontend/pages/inventory/index.vue
  - backend/app/modules/inventory/frontend/composables/useInventory.ts
last_verified_commit: 0000000
---

# /inventory

Clinic stock tracking — items, categories, quantities, and low-stock
alerts. Base version: no cost tracking or stock movements yet
(see issue #226 for the core upgrade).

## Permissions

- `inventory.read` — view the list, dashboard stats, and low-stock
  alerts (`admin` plus every other role by default).
- `inventory.write` — create, update items, adjust stock (`admin`
  only by default).
- `inventory.delete` — soft-delete items (`admin` only by default).

## What this screen does

- **Dashboard stats** — total items, low-stock count, out-of-stock
  count, and total quantity across the clinic.
- **Low-stock alerts** — items at or below their minimum quantity are
  highlighted with an orange warning badge.
- **Filter** the list by category, low-stock only toggle, and search
  (matches code, name, or supplier).
- **Add item** — opens a modal for code, name, category, initial
  quantity, minimum quantity, unit, location, supplier, and description.
- **Adjust stock** — per-row action to add or subtract quantity with
  an optional reason. The adjustment is atomic at the DB level (race
  condition guard from issue #153).
- **Edit / delete** per row, gated behind `inventory.write` /
  `inventory.delete`.
- **Pagination** — the list is paginated (default 20 per page, max
  200).
