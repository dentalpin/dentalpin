# purchase_orders module

Procurement purchase orders - the execution layer for the supplier suite
(#227). Places orders, tracks the status lifecycle, receives partial
deliveries with quality checks, and exports PDFs. Consumed by
`supplier_ratings` (#227-5) and `inventory_reorder` (#227-4).

## Public API

Routes mounted at `/api/v1/purchase_orders/`.

- `GET    /purchase_orders`           — list, filterable by `order_status` / `supplier_id`, paginated; `purchase_orders.read`
- `GET    /purchase_orders/{id}`      — order + lines + supplier/item names; `purchase_orders.read`
- `POST   /purchase_orders`           — create a `draft` order (201); `purchase_orders.write`
- `PATCH  /purchase_orders/{id}`      — edit `expected_date` / `notes` (lock: 409 once received); `purchase_orders.write`
- `POST   /purchase_orders/{id}/status` — explicit transition; 409 on invalid moves; `purchase_orders.write`
- `POST   /purchase_orders/{id}/receive` — batch receive; only `good` lines move stock; `purchase_orders.write`
- `GET    /purchase_orders/{id}/receipts`          — receipt batches; `purchase_orders.read`
- `GET    /purchase_orders/{id}/receipts/{rid}`    — one batch with line quality; `purchase_orders.read`
- `GET    /purchase_orders/{id}/pdf`   — WeasyPrint PDF (self-contained, en/es, clinic currency); `purchase_orders.read`

### Status lifecycle

```
draft ──> sent ──> confirmed ──> received   (implicit: receipt completes all lines)
  │         │         │
  └─────────┴─────> cancelled
```

Explicit transitions go through `POST /status` with the allowed matrix
(`draft->sent`, `draft->cancelled`, `sent->draft`, `sent->confirmed`,
`sent->cancelled`, `confirmed->cancelled`). `received` can **only** be
reached through a receive batch that fulfils every line — there is no
manual "mark received" escape hatch.

## Data model

- `purchase_orders` — header: `supplier_id` (FK to `contacts.id`, type
  `supplier`), `status`, `expected_date`, `notes`, `created_by`,
  `received_at`.
- `purchase_order_lines` — one row per item: `purchase_order_id`,
  `inventory_item_id`, `quantity_ordered`, `quantity_received`,
  `unit_price` (snapshot, `Numeric(12, 2)` matching inventory's
  `unit_cost`). `UNIQUE (purchase_order_id, inventory_item_id)`.
- `purchase_receipts` — a delivery batch against a PO (partial receives
  supported; `received_at` server-stamped, `received_by`).
- `purchase_receipt_lines` — per-line `quantity_received` + `quality`
  (`good` | `rejected`). This is the audit trail for "only good hits
  stock": rejected units never touch the inventory ledger.

Migration: `po_0001_initial` on own Alembic branch (`purchase_orders`),
depending on `contacts@con_0001` + `inventory@inv_0002`.

## Stock integration

Receiving calls `InventoryService.apply_movement` directly (the single
quantity-change write path in inventory, which appends the
`stock_movements` ledger row under the same row lock):

- `reason='purchase_receipt'`, `reference_type='purchase_receipt'`,
  `reference_id=<receipt.id>` — the ledger back-references the batch.
- Only `quality='good'` units move stock **and** count towards the line's
  `quantity_received`. `rejected` units are recorded on the receipt line
  (audit trail) but leave the line open, so the replacement delivery can be
  received; supplier_ratings (#227-5) is the venue for deductions.
- The whole batch is one transaction: receipt + lines + stock movements +
  the auto `received` transition commit or roll back together (ADR 0019).

## Dependencies

`manifest.depends = ["contacts", "inventory", "suppliers"]` — imports
`Contact` (supplier validation + name denormalization), `InventoryItem`
and `InventoryService.apply_movement`.

## Permissions

`purchase_orders.read`, `purchase_orders.write`. Role grants mirror
`suppliers`: admin wildcard; dentist/hygienist read-only;
assistant/receptionist read+write (front-desk runs procurement).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_purchase_orders` | READ | `PurchaseOrderService.list_order_responses` | `purchase_orders.read` |
| `get_purchase_order` | READ | `PurchaseOrderService.get_order_response` | `purchase_orders.read` |
| `create_purchase_order` | WRITE | `PurchaseOrderService.create_order` | `purchase_orders.write` |
| `transition_purchase_order` | WRITE | `PurchaseOrderService.transition_order` | `purchase_orders.write` |
| `receive_purchase_order` | WRITE | `PurchaseOrderService.receive_order` | `purchase_orders.write` |

All five are marked `exposes_free_text=True`: item/supplier names and
notes are user-entered prose kept off the cloud LLM path under redaction.
Tool ids/prices return as native UUID/Decimal for jsonify.

## Events emitted

- `purchase_order.created` — payload `(clinic_id, order_id, supplier_id, status)`.
- `purchase_order.status_changed` — payload
  `(clinic_id, order_id, supplier_id, from_status, status)`.
- `purchase_order.received` — payload `(clinic_id, order_id, supplier_id,
  receipt_id, applied[{inventory_item_id, quantity}], fully_received)`.

All three publish **inside** the transaction per ADR 0019 (transactional
subscribers see the uncommitted rows and roll back with them).

## Events consumed

None today. `inventory_reorder` (#227-4) is expected to subscribe to
`purchase_order.received` to clear open suggestions.

## Lifecycle

- `installable=True`, `auto_install=False` (optional module, activated
  manually from the admin UI), `removable=True`.
- Migrations on the `purchase_orders` Alembic branch, depending on
  `contacts@con_0001` + `inventory@inv_0002`.

## CHANGELOG

See `./CHANGELOG.md`.