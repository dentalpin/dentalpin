---
module: purchase_orders
last_verified_commit: 8b8e9375
---

# purchase_orders — overview

Procurement purchase orders: the execution layer for the supplier suite
(#227). Places orders against supplier contacts, tracks a status lifecycle,
receives partial deliveries with quality checks, and exports PDFs.

## What it is

Authenticated endpoints under `/api/v1/purchase_orders/` (JWT + RBAC). A
clinic places an order for inventory items, moves it through
`draft -> sent -> confirmed -> received|cancelled`, and receives delivery
batches where only `good` lines move stock.

Routes:
- `GET /api/v1/purchase_orders` — list, filterable by `order_status`/`supplier_id`
- `GET /api/v1/purchase_orders/{id}` — order + lines + supplier/item names
- `POST /api/v1/purchase_orders` — create a `draft` order (201)
- `PATCH /api/v1/purchase_orders/{id}` — edit `expected_date`/`notes` (409 once received)
- `POST /api/v1/purchase_orders/{id}/status` — explicit status transition (409 on invalid moves)
- `POST /api/v1/purchase_orders/{id}/receive` — batch receive; only `good` lines move stock
- `GET /api/v1/purchase_orders/{id}/receipts` — receipt batches
- `GET /api/v1/purchase_orders/{id}/receipts/{rid}` — one batch with line quality
- `GET /api/v1/purchase_orders/{id}/pdf` — WeasyPrint PDF (en/es, clinic currency)

### Status lifecycle

```
draft ──> sent ──> confirmed ──> received   (implicit: receipt completes all lines)
  │         │         │
  └─────────┴─────> cancelled
```

Explicit transitions go through the allowed matrix; `received` can **only**
be reached through a receive batch that fulfils every line — there is no
manual "mark received" escape hatch.

## Data model

- `purchase_orders` — header: `supplier_id` (FK to `contacts.id`, type
  `supplier`), `status`, `expected_date`, `notes`, `created_by`,
  `received_at`.
- `purchase_order_lines` — one row per item: `purchase_order_id`,
  `inventory_item_id`, `quantity_ordered`, `quantity_received`,
  `unit_price` snapshot. `UNIQUE (purchase_order_id, inventory_item_id)`.
- `purchase_receipts` — a delivery batch against a PO (partial receives
  supported; `received_at` server-stamped, `received_by`).
- `purchase_receipt_lines` — per-line `quantity_received` + `quality`
  (`good` | `rejected`). Rejected units never touch the inventory ledger
  and do not fulfil the PO line: the order stays open for the replacement.

Migration: `po_0001_initial` on own Alembic branch (`purchase_orders`),
depending on `contacts@con_0001` + `inventory@inv_0002`.

## Stock integration

Receiving calls `InventoryService._apply_movement` (the single
quantity-change write path in inventory) with `reason='purchase_receipt'`,
`reference_type='purchase_receipt'`, `reference_id=<receipt.id>`. Only
`quality='good'` quantities are applied. The whole batch is one transaction:
receipt + lines + stock movements + the auto `received` transition commit
or roll back together (ADR 0019).

## Service layer

`PurchaseOrderService` encapsulates the lifecycle: clinic-scoped
supplier/item validation at creation, duplicate-item guard, explicit
transitions with an allowed-matrix (409 on invalid moves), batch receiving
with over-receipt guard, and a lock on editing received orders.

## Agent tools

Five tools: `list_purchase_orders`, `get_purchase_order`,
`create_purchase_order`, `transition_purchase_order`,
`receive_purchase_order`. Each wraps the corresponding service method,
filters by `ctx.clinic_id`, gated by the matching RBAC string, and returns
native UUID/Decimal values (jsonify at the registry). All are marked
`exposes_free_text=True` (item/supplier names and notes are user-entered
prose kept off the cloud LLM path).

## Tenancy

Every query filters by `clinic_id`; a cross-clinic supplier or item during
creation 404s/400s and never leaks another clinic's rows.

## Pricing note / follow-up (#227-2 integration)

PO lines carry a `unit_price` **snapshot** supplied at creation (or left
null), and the create tool does not source it from anywhere — it is
independent of `supplier_items`' per-vendor SKU/price (@#368). This keeps
purchase_orders uncoupled from `supplier_items` for v1. **Follow-up:** once
`supplier_items` (#227-2) ships, wire PO-line creation to source the
per-vendor unit price automatically from the supplier-item link
(`supplier_id` + `inventory_item_id`), with the manual snapshot as a
fallback. That change touches `PurchaseOrderService.create_order` + the
`create_purchase_order` tool only; no schema migration needed
(`unit_price` already exists on `purchase_order_lines`).

## Constraints

Own Alembic branch (`purchase_orders`), depending on `contacts@con_0001` +
`inventory@inv_0002` — FKs only into `contacts`, `inventory_items`, and `users`.
`manifest.depends = ["contacts", "inventory", "suppliers"]` (suppliers is
declared for domain semantics; the code references suppliers purely as
`Contact(contact_type='supplier')`). No hard DELETE — POs use the status
lifecycle (L7): a cancelled/received order is never removed.

See [`./permissions.md`](./permissions.md) and [`./events.md`](./events.md)
for full detail.