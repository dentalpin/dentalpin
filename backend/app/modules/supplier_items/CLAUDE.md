# supplier_items module

Procurement pricing catalogue — links each inventory item to the suppliers
that source it (`supplier_id` -> `inventory_item_id`), carrying the supplier's
own `supplier_sku` and quoted `price`. Supports the "multiple vendors per
item" model and feeds `purchase_orders` (#227-3) and `inventory_reorder`
(#227-4). Part of the procurement suite (#227-2).

## What it does

Routes mounted at `/api/v1/supplier_items/`.

- `GET    /supplier_items`          — list, filterable by `supplier_id` and `inventory_item_id`; `supplier_items.read`
- `GET    /supplier_items/{id}`     — single link (SKU + price); `supplier_items.read`
- `POST   /supplier_items`          — create a link (201); `supplier_items.write`
- `PATCH  /supplier_items/{id}`     — update SKU / price; `supplier_items.write`
- `DELETE /supplier_items/{id}`     — soft-delete (sets `is_active=false`, returns 204); `supplier_items.write`

Deletion is soft (not a real database delete) so historical purchase orders
can still reference which supplier/item the link described, even after the
link is removed. A `(supplier, item)` pair is unique — a duplicate surfaces
as a 409 from the UNIQUE constraint. Creating a link for a pair whose row
was soft-deleted revives that row with the new SKU/price (same `id`).

## Data model

`SupplierItem` is a link table between `suppliers.id` and
`inventory_items.id`. Fields:

- `id`: UUID (PK)
- `clinic_id`: UUID (denormalized for rapid multi-tenant filtering)
- `supplier_id`: UUID (FK to `suppliers.id`)
- `inventory_item_id`: UUID (FK to `inventory_items.id`)
- `supplier_sku`: String(100), nullable — the supplier's code for the item
- `price`: `Numeric(12,2)`, nullable — unit price this supplier quotes
- `is_active`: Boolean, default true — soft-delete flag

UNIQUE constraint on `(supplier_id, inventory_item_id)` enforces one pricing
row per pair.

## Dependencies

`manifest.depends = ["contacts", "inventory", "suppliers"]`. The module
imports `Supplier` (the FK target, validated in-clinic at creation),
`Contact` (for the supplier `name` join) and `InventoryItem` (the item end
of the link). All three are declared deps.

## Permissions

`supplier_items.read`, `supplier_items.write`. Role grants mirror
`suppliers`/`contacts`: admin gets wildcard; dentist/hygienist get read-only;
assistant/receptionist get read+write (front-desk staff maintain the vendor
pricing catalogue day-to-day).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_supplier_items` | READ | `SupplierItemService.list_links` | `supplier_items.read` |
| `get_supplier_item` | READ | `SupplierItemService.get_link` | `supplier_items.read` |
| `create_supplier_item` | WRITE | `SupplierItemService.create_link` | `supplier_items.write` |
| `update_supplier_item` | WRITE | `SupplierItemService.update_link` | `supplier_items.write` |

All tools are `exposes_free_text=True` (supplier/item names are user-entered
prose). `update_supplier_item` forwards only the fields the agent set
(`exclude_unset`, M4).

## Events emitted / consumed

None.

## Lifecycle

- `installable=True`, `auto_install=False` (optional module, activated
  manually from the admin UI), `removable=True`.
- Migrations on the `supplier_items` Alembic branch, depending on
  `suppliers@supp_0001` + `inventory@inv_0002` (enforces that both target
  tables exist before we create the FKs).

## Frontend

No Nuxt layer — intentionally deferred until all five backend procurement
modules (#227-1..#227-5) land, at which point the supplier suite ships a
shared frontend. Backend PR only.

## CHANGELOG

See `./CHANGELOG.md`.