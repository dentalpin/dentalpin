---
module: inventory_reorder
last_verified_commit: 0f333000
---

# inventory_reorder — Reorder suggestions

> **Module:** `inventory_reorder` · **Route prefix:** `/api/v1/inventory_reorder/` · **Category:** official · **Removable:** yes

Part of the supplier & procurement suite (#227). Computes **reorder
suggestions** — how much of each inventory item to order — from the
inventory movement ledger, the supplier's sourcing and lead time, and
what is already on open purchase orders. It is the *policy* layer of
replenishment: it decides *what to order, from whom, and how many*; the
`purchase_orders` module owns the resulting order lifecycle (status
transitions, receipts, PDFs).

## Why a separate module

Reorder logic lives in the recommendations/policy plane and has zero
runtime tables of its own. Keeping it a module (rather than a service
blob inside `purchase_orders`) preserves the suite's modular boundary:
`sales`/frontend and the Copilot agent can query suggestions without
forcing procurement internals into their domain, and the module can be
disabled independently for clinics that prefer manual purchasing.

## What it does

| Capability | Description |
|---|---|
| `GET /suggestions` | Recompute and return per-item reorder suggestions for the clinic's active inventory items. |
| `POST /orders` | Turn the requested suggestions into draft purchase orders, grouped **one PO per supplier**. Returns the created POs (201). |

The module emits **no events** and has **no tables** — it is pure
computation over existing state (see `events.md`). Creating POs through
`POST /orders` reuses `PurchaseOrderService.create_order`, which is where
the `purchase_order.created` event is published (ADRs 0002/0003, 0019).

## The suggestion formula

For each **active** inventory item in the clinic:

1. **`usage_90d`** — sum of the item's negative movement deltas in the
   last 90 days. This covers consumption via sales/treatments and any
   other deduction; positive deltas (stock-in) are ignored. If there is
   **no usage** in the window, the item is **skipped** (no demand ⇒ no
   suggestion).
2. **Sourcing** — the item's supplier link is chosen as: the
   `preferred` supplier if any link marks one, otherwise the first link
   ordered by supplier name. Items with **no supplier link** are
   **skipped** (the engine cannot order from nobody).
3. **`lead_time_days`** — the chosen supplier's lead time. If the
   supplier has **no lead time set**, it is treated as `0`, so the item
   is **skipped** (`reorder_point = 0`, suggestion stays `≤ 0`).
4. **`daily_usage`** — `usage_90d / 90`, rounded to 2 decimals.
5. **`reorder_point`** — `ceil(daily_usage × lead_time_days)`: the stock
   level at which to reorder so that expected consumption during the
   lead time is covered.
6. **`on_order`** — quantity already committed to **open** purchase
   orders (`draft` / `sent` / `confirmed`): `Σ(quantity_ordered −
   quantity_received)`.
7. **`suggested_quantity`** — `ceil(reorder_point − (stock_quantity +
   on_order))`. Only suggestions with `suggested_quantity > 0` are
   returned; the positive check is what makes an in-stock item
   disappear from the list once a PO covers the projected shortfall
   (re-runs of `/suggestions` shrink as `on_order` fills).

All figures are returned as native values — UUIDs, `Decimal` quantities
— for `jsonify` at the registry. Suggestions are sorted by item name.

## CLI / API notes

- Multi-tenancy: every query filters by `clinic_id` from
  `get_clinic_context`; suggestions for one clinic never leak another's
  ledger, suppliers or POs.
- `POST /orders` returns **400** when any requested item id has no
  current suggestion — the caller must re-fetch `/suggestions` and pick
  a currently suggested item. One supplier per PO; when two items share
  a supplier they land on the same draft.
- All endpoints are read/write gated per `permissions.md`.

## Dependencies

`manifest.depends = ["contacts", "inventory", "suppliers", "supplier_items", "purchase_orders"]` — reads `InventoryItem` + `StockMovement` (inventory), `SupplierItem` (sourcing), `Supplier` + `Contact` (lead time + display name), and `PurchaseOrder(Line)` + `PurchaseOrderService` (on-order and PO creation). All legal because they are declared.

## Lifecycle

- `installable=True`, `auto_install=False` (optional, activated from the admin UI), `removable=True`.
- No tables; a single no-op Alembic revision (`ir_0001`, own `inventory_reorder` branch) exists purely so the `module_branch_is_isolated` check can validate a clean downgrade on uninstall (same pattern as `recall_reminders`).

## Copilot

Two agent tools are exposed, mirroring the HTTP surface:
`list_reorder_suggestions` (READ) and `generate_reorder_orders` (WRITE).
Both are marked `exposes_free_text=True` (item/supplier names are
user-entered prose kept off the cloud LLM path). See the module
`CLAUDE.md` for the table + the `ToolCategory`/permission mapping.