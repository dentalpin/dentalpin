# Inventory module

Simple stock-on-hand list: item name, category, unit, quantity on hand,
and a low-stock threshold that flags items needing reorder. Custom
clinic module — standalone, no dependency on any other module.

## Public API

Routes mounted at `/api/v1/inventory/`.

- `GET    /inventory`               — list, filterable by category/search/low-stock; `inventory.read`
- `POST   /inventory`                — create; `inventory.write`
- `PATCH  /inventory/{id}`           — edit name/category/unit/threshold/notes; `inventory.write`
- `POST   /inventory/{id}/adjust`    — adjust quantity by a signed delta; `inventory.write`
- `DELETE /inventory/{id}`           — delete; `inventory.write`

Quantity is changed via `/adjust` (signed delta), not by setting it
directly through `PATCH` — this keeps the day-to-day action ("used 2",
"restocked 20") separate from editing the item's static details,
and the service rejects any adjustment that would make the quantity
go negative.

## Dependencies

`manifest.depends = []` — standalone.

## Permissions

`inventory.read`, `inventory.write`. Default role grants: admin full
access; dentist/hygienist read-only; assistant/receptionist read+write.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_inventory` | READ | `InventoryService.list_items` | `inventory.read` |
| `adjust_inventory` | WRITE | `InventoryService.adjust_quantity` | `inventory.write` |

## Events emitted / consumed

None (a natural future extension: publish `inventory.low_stock` when an
adjustment crosses the threshold, for Phase 5's task board to pick up).

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- Migrations on the `inventory` Alembic branch, chained off the core
  `0001` migration — no cross-module foreign keys.

## CHANGELOG

See `./CHANGELOG.md`.
