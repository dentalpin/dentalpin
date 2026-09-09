---
module: supplier_ratings
last_verified_commit: 0f333000
---

# supplier_ratings — Delivery, quality & communication ratings

> **Module:** `supplier_ratings` · **Route prefix:** `/api/v1/supplier_ratings/` · **Category:** official · **Removable:** yes

Part of the supplier & procurement suite (#227). Gives every supplier a
**manual 1–5 communication rating** (one per clinic) plus an automatic
**delivery/quality scorecard** computed live from purchase order history.
It is the last module of the chain: `purchase_orders` produces the data
(orders, receipts, quality verdicts), `supplier_ratings` interprets it.

## What it does

| Capability | Description |
|---|---|
| `GET /supplier_ratings` | Paginated list of the clinic's active supplier contacts with their delivery/quality metrics and current review. |
| `GET /supplier_ratings/{id}` | One supplier's full scorecard + current review (404 if not a supplier here). |
| `POST /supplier_ratings/reviews` | Set the manual 1–5 rating for a supplier (201; 409 when it already has one). |
| `PATCH /supplier_ratings/reviews/{rid}` | Edit the score/comment of an existing review. |
| `DELETE /supplier_ratings/reviews/{rid}` | Remove a review (204). |

The module emits **no events** and stores **only** the manual review rows
(`supplier_reviews`); delivery/quality metrics are pure computation over
the purchase order ledger (`see events.md`).

## The scorecard

Metrics are aggregated per supplier on every read; nothing is cached, so
the numbers always match the PO ledger and self-correct as deliveries land.

| Metric | Meaning |
|---|---|
| `po_count` | Total purchase orders placed with the supplier. |
| `received_count` | POs that reached `status='received'`. |
| `received_with_due_date` | Received POs that carried an `expected_date`. |
| `on_time_deliveries` | Received POs whose `received_at::date <= expected_date`. |
| `on_time_rate` | `on_time_deliveries / received_with_due_date` (None if denominator is 0). |
| `received_quantity` | Sum of `quantity_received` over all receipt lines, all qualities. |
| `rejected_quantity` | Same, but only lines marked `quality='rejected'`. |
| `reject_rate` | `rejected_quantity / received_quantity` (None if received is 0). |

Key semantics:

- A delivery only counts as on-time if the PO was **received** **and**
  had an `expected_date`. Received POs with no due date are excluded from
  the on-time denominator rather than counted as late.
- Rejections come from the quality verdicts recorded at
  `POST /purchase-orders/{id}/receive` (the audit trail for "only good
  hits stock"); rejected units never shipped into stock, so they are
  naturally excluded from `on_time` but included in `reject_rate`.
- Rates are `Decimal` quantized to 2 decimals (half-up).
- Every query filters by `clinic_id` from `get_clinic_context`; the
  scorecard for one clinic never leaks another's suppliers, orders or
  receipts.

## The manual rating

`scores` are integers `1..5` (`CHECK` in the DDL, `ge=1 le=5` in the
schema). The `UNIQUE (clinic_id, supplier_id)` constraint enforces **one
current rating per supplier**: creating a second one returns **409** and
the caller must PATCH the existing review instead. Comments are free text.

## Dependencies

`manifest.depends = ["contacts", "purchase_orders"]` — reads `Contact`
(supplier identity) and `PurchaseOrder`/`PurchaseReceipt`/
`PurchaseReceiptLine` (metrics). The supplier FK targets `contacts.id`
directly; there is no `suppliers` extension-row dependency here.

## Lifecycle

- `installable=True`, `auto_install=False` (optional, activated from the admin UI), `removable=True`.
- Migration `rat_0001` on its own `supplier_ratings` Alembic branch,
  `depends_on=("con_0001",)` (the supplier FK needs `contacts` first);
  registered in `backend/alembic.ini`.

## Copilot

Three agent tools mirror the HTTP surface:
`list_supplier_ratings` (READ), `get_supplier_rating` (READ) and
`create_supplier_review` (WRITE). All are `exposes_free_text=True`
(supplier names/comments are user-entered prose kept off the cloud LLM
path). See the module `CLAUDE.md` for the permission mapping.