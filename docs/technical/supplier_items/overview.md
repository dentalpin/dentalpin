---
module: supplier_items
last_verified_commit: 1642fd42
---

# supplier_items — overview

Procurement pricing catalogue: links each inventory item to the suppliers
that source it, carrying the supplier's own SKU and quoted unit price. Enables
the "multiple vendors per item" model and feeds purchase_orders (#227-3) and
inventory_reorder (#227-4).

## What it is

Admin-authenticated CRUD under `/api/v1/supplier_items/` (JWT + RBAC).
A clinic links its suppliers to inventory items, one pricing row per
`(supplier, item)` pair.

Routes:
- `GET /api/v1/supplier_items` — list with `supplier_id` / `inventory_item_id` filtering
- `GET /api/v1/supplier_items/{id}` — get one
- `POST /api/v1/supplier_items` — create a link (201)
- `PATCH /api/v1/supplier_items/{id}` — update SKU / price
- `DELETE /api/v1/supplier_items/{id}` — soft-delete the link (204, sets `is_active=false`)

## Data model

`supplier_items` — link table between `suppliers.id` and `inventory_items.id`.
Fields: `supplier_sku`, `price` (`Numeric(12,2)`), `is_active` (soft delete).
A UNIQUE `(supplier_id, inventory_item_id)` constraint enforces one pricing
row per pair; a duplicate pair surfaces as a 409. Denormalizes `clinic_id`
for rapid multi-tenant filtering.

Migration: `sui_0001_initial` on its own Alembic branch (`supplier_items`),
depending on `suppliers@supp_0001` + `inventory@inv_0002`.

## Service layer

`SupplierItemService` encapsulates the link lifecycle:
- `create_link`: Validates both ends exist in-clinic (the `suppliers` row
  and the `inventory_items` row), revives a soft-deleted row for the same
  pair instead of 409ing, and returns `(link, supplier_name, item_name)` so
  routers/tools build denormalized responses without extra queries.
- `list_links`: Paginated join query, optional `supplier_id` /
  `inventory_item_id` filters, active-only.
- `get_link`: Retrieves one active link, clinic-scoped; a cross-clinic or
  inactive id 404s.
- `update_link`: Updates SKU / price, forwarding only supplied fields
  (`exclude_unset`, M4).
- `deactivate_link`: Soft-delete — sets `is_active=false` (L7), keeping the
  row for historical purchase-order references.

Duplicate pairs surface as a 409 from the UNIQUE constraint (not a
select-then-insert race). The soft delete keeps historical references intact.

## Agent tools

Four tools exposed: `list_supplier_items`, `get_supplier_item`,
`create_supplier_item`, `update_supplier_item`. Each wraps the corresponding
service method, filters by `ctx.clinic_id`, returns native values (coerced at
the registry), and is marked `exposes_free_text=True` because supplier/item
names are user-entered prose kept off the cloud LLM path under redaction.

## Tenancy

Every query filters by `clinic_id`; a cross-clinic supplier or item id 404s
rather than 403s, matching repo convention. Both ends of a link are validated
in-clinic at creation (L1).

## Constraints

Own Alembic branch (`supplier_items`) depending on `suppliers@supp_0001` +
`inventory@inv_0002` — the module imports the `Supplier`, `Contact` and
`InventoryItem` models. `manifest.depends =
["contacts", "inventory", "suppliers"]`.

See [`./permissions.md`](./permissions.md) and [`./events.md`](./events.md)
for full detail.