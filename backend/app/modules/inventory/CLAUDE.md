# inventory module

Standalone stock list with per-item minimum quantities and low-stock
alerts (roadmap #220, base version). Cost tracking, cost/movement audit,
and consumable auto-deduction landed with the core upgrade (#226).

## Public API

Routes mounted at `/api/v1/inventory/`.

- `GET    /inventory`                    — list; filters: `category`, `low_stock=true`, `include_inactive=true`, paginated; `inventory.read`
- `GET    /inventory/valuation`          — on-hand value over active items with a known `unit_cost`; `inventory.read`
- `GET    /inventory/{id}`               — detail; `inventory.read`
- `GET    /inventory/{id}/movements`     — audit trail (paginated, filterable by `reason`, actor names resolved); `inventory.read`
- `POST   /inventory`                    — create (201, opening stock becomes an `initial` ledger row); `inventory.write`
- `PATCH  /inventory/{id}`               — edit metadata / absolute quantity set (ledgered as `correction`) / `is_active`; `inventory.write`
- `POST   /inventory/{id}/adjust`        — atomic relative stock change (+/-) with reason+note, 409 if it would go negative; `inventory.write`
- `DELETE /inventory/{id}`               — delete (204); 409 `item_has_history` when the item has ledger rows — deactivate instead; `inventory.write`

## Concurrency

Stock changes are guarded at the DB level: a
`ck_inventory_items_stock_non_negative` CHECK constraint plus a
`SELECT … FOR UPDATE` row lock in `InventoryService.apply_movement`,
the single write path every quantity change goes through (it also
appends the `stock_movements` ledger row in the same transaction).
Never read-modify-write without the lock — this is the PR #153 race
post-mortem. Auto-deduction idempotency: partial unique index
`uq_stock_movements_consumption_ref` + check-then-act under the row
lock, `ON CONFLICT DO NOTHING` as the concurrency backstop.

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
| `adjust_inventory_stock` | WRITE | `InventoryService.adjust_stock` | `inventory.write` |
| `get_stock_movements` | READ | `InventoryService.list_movements` | `inventory.read` |

All four are marked `exposes_free_text=True`: item names/notes are
user-entered prose that may name people, so they stay off the cloud LLM
path under redaction. Tool ids return as native UUIDs for jsonify.

## Events emitted

- `inventory.low_stock` (`EventType.INVENTORY_STOCK_LOW`) — once per
  not-low → low crossing; transactional per ADR 0019.

## Events consumed

None — auto-deduction on `odontogram.treatment.performed` lives in
`treatment_consumables` (subscription inversion, #226), which calls
`InventoryService.apply_consumption` with pre-resolved links.

## Lifecycle

- `installable=True`, `auto_install=False` (ships inactive, activated
  from the module admin UI), `removable=True`.
- Migrations on the `inventory` Alembic branch rooted on core `0001`.
- `tests/modules/inventory/test_uninstall_roundtrip.py` covers the
  branch-scoped downgrade/upgrade round trip (branch-relative `@-1`
  walk).

## CHANGELOG

See `./CHANGELOG.md`.