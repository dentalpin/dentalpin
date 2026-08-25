# inventory module

Standalone stock list with per-item minimum quantities and low-stock
alerts (roadmap #220, base version). Cost tracking, stock movements and
auto-deduction arrive later (#226).

## Public API

Routes mounted at `/api/v1/inventory/`.

- `GET    /inventory`                    — list; filters: `category`, `low_stock=true`, paginated; `inventory.read`
- `GET    /inventory/{id}`               — detail; `inventory.read`
- `POST   /inventory`                    — create (201); `inventory.write`
- `PATCH  /inventory/{id}`               — edit metadata / absolute quantity set; `inventory.write`
- `POST   /inventory/{id}/adjust`        — atomic relative stock change (+/-), 409 if it would go negative; `inventory.write`
- `DELETE /inventory/{id}`               — delete (204); `inventory.write`

## Concurrency

Stock changes are guarded at the DB level: a
`ck_inventory_items_stock_non_negative` CHECK constraint plus an atomic
single-UPDATE adjust path (`SET stock_quantity = stock_quantity + delta
WHERE ... AND stock_quantity + delta >= 0 RETURNING *`). Never
read-modify-write in app code — this is the PR #153 race post-mortem.

## Dependencies

`manifest.depends = []` — standalone. FKs point only at core tables.

## Permissions

`inventory.read`, `inventory.write`. Whole team read+write by default;
stock levels are operational data (see permissions.md).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_inventory_items` | READ | `InventoryService.list_items` | `inventory.read` |
| `create_inventory_item` | WRITE | `InventoryService.create_item` | `inventory.write` |
| `adjust_inventory_stock` | WRITE | `InventoryService.adjust_stock` | `inventory.write` |`n| `get_stock_movements` | READ | `InventoryService.list_movements` | `inventory.read` |

All three are marked `exposes_free_text=True`: item names/notes are
user-entered prose that may name people, so they stay off the cloud LLM
path under redaction. Tool ids return as native UUIDs for jsonify.

## Events emitted

- `inventory.low_stock` (`EventType.INVENTORY_STOCK_LOW`) — once per
  not-low → low crossing; transactional per ADR 0019.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=False` (ships inactive, activated
  from the module admin UI), `removable=True`.
- Migrations on the `inventory` Alembic branch rooted on core `0001`.
- `tests/modules/inventory/test_uninstall_roundtrip.py` covers the
  branch-scoped downgrade/upgrade round trip (branch-relative `@-1`
  walk).

## CHANGELOG

See `./CHANGELOG.md`.