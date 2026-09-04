# inventory_reorder module

Reorder suggestions for the supplier suite (#227-4) — the **policy**
layer of replenishment. Computes per-item reorder quantities from 90-day
consumption, preferred-supplier lead times, and quantities already on
open purchase orders; can turn a selection of suggestions into draft POs
(one per supplier). Pure computation — no tables of its own.

## Public API

Routes mounted at `/api/v1/inventory_reorder/` (the loader uses
`prefix=f"/api/v1/{module.name}"`, so the literal underscore form).

- `GET  /inventory_reorder/suggestions` — recompute suggestions for
  active items; `inventory_reorder.read`.
- `POST /inventory_reorder/orders` — body `ReorderOrdersCreate
  {item_ids: [UUID]}`; creates draft POs grouped one per supplier (201);
  `inventory_reorder.write`. 400 when an item_id has no current
  suggestion.

### Suggestion formula

For each active item, in order:

1. `usage_90d` — `Σ(-delta)` over the last 90 days of movements with
   `delta < 0`. No usage → item **skipped** (no demand).
2. Sourcing — `preferred` supplier link first, else first link ordered
   by supplier name. No link → **skipped**.
3. `lead_time_days` — chosen supplier's value; `None` → treated as `0`,
   so `reorder_point = 0` and the item is **skipped**.
4. `daily_usage = usage_90d / 90` (2 dp, half-up).
5. `reorder_point = ceil(daily_usage × lead_time_days)`.
6. `on_order = Σ(quantity_ordered − quantity_received)` over PO lines on
   open orders (`draft` / `sent` / `confirmed`).
7. `suggested_quantity = ceil(reorder_point − (stock_quantity +
   on_order))`; only `> 0` returned.

Everything returns native values (UUID/Decimal) — `jsonify` at the
registry coerces them; never hand-`str()`/`float()`.

## Data model

None. Reads `InventoryItem`/`StockMovement` (inventory),
`SupplierItem` (sourcing), `Supplier` + `Contact` (lead time + name),
`PurchaseOrder(Line)` (on-order). No writes except through
`PurchaseOrderService.create_order`.

## Dependencies

`manifest.depends = ["contacts", "inventory", "suppliers", "supplier_items", "purchase_orders"]` — all imports are direct service/table reads covered by declared deps.

## Permissions

`inventory_reorder.read`, `inventory_reorder.write`. Grants mirror
`purchase_orders`: admin wildcard; dentist/hygienist read-only;
assistant/receptionist read+write (front desk runs replenishment).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_reorder_suggestions` | READ | `ReorderService.compute_suggestions` | `inventory_reorder.read` |
| `generate_reorder_orders` | WRITE | `ReorderService.generate_orders` | `inventory_reorder.write` |

Both are `exposes_free_text=True`: item/supplier names are user-entered
prose kept off the cloud LLM path under redaction. Values return as
native UUID/Decimal for jsonify.

## Events emitted

None. `purchase_order.created` is still published when POs are created —
but by `purchase_orders` itself (inside the transaction, ADR 0019).

## Events consumed

None. Suggestions are computed on demand, so nothing needs clearing on
`purchase_order.received` — the list self-corrects because `on_order` /
`stock_quantity` are derived, not cached. (The "expected to subscribe"
note in `docs/technical/purchase_orders/events.md` predates this module
and is superseded by the design above.)

## Lifecycle

- `installable=True`, `auto_install=False` (optional, activated from the
  admin UI), `removable=True`.
- No tables; single no-op Alembic revision `ir_0001` on its own
  `inventory_reorder` branch (registered in `backend/alembic.ini`
  `version_locations`), so `module_branch_is_isolated` can validate a
  clean uninstall downgrade — same pattern as `recall_reminders`.

## CHANGELOG

See `./CHANGELOG.md`.