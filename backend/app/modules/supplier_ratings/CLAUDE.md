# supplier_ratings module

Manual 1–5 communication rating per supplier, plus automatic
delivery/quality metrics computed on demand from purchase order history
(#227-5). Last module of the supplier & procurement suite.

## Public API

Routes mounted at `/api/v1/supplier_ratings/` (the loader uses
`prefix=f"/api/v1/{module.name}"`, so the literal underscore form).

- `GET    /supplier_ratings`                            — paginated list: each
  supplier contact with its delivery/quality metrics and current review;
  `supplier_ratings.read`.
- `GET    /supplier_ratings/{supplier_id}`              — one supplier's
  metrics + current review; `supplier_ratings.read`. 404 when the id is
  not a supplier contact in this clinic.
- `POST   /supplier_ratings/reviews`                    — set the 1–5 review
  (body `SupplierReviewCreate {supplier_id, score, comment}`), 201;
  `supplier_ratings.write`. 409 when the supplier already has a rating.
- `PATCH  /supplier_ratings/reviews/{review_id}`        — edit score/comment;
  `supplier_ratings.write`.
- `DELETE /supplier_ratings/reviews/{review_id}`        — 204;
  `supplier_ratings.write`.

## Metrics

Computed on demand (read-only), clinic-scoped, from `purchase_orders`,
`purchase_receipts` and `purchase_receipt_lines`. Nothing is persisted, so
there is no stale-cache problem: metrics always reflect the PO ledger and
self-correct as orders are received.

| Metric | Source |
|---|---|
| `po_count` | PO headers for the supplier |
| `received_count` | POs with `status='received'` |
| `received_with_due_date` | received POs that had an `expected_date` |
| `on_time_deliveries` | received POs with `received_at::date <= expected_date` |
| `on_time_rate` | `on_time_deliveries / received_with_due_date` (None if 0) |
| `received_quantity` | `SUM(quantity_received)` over receipt lines, all qualities |
| `rejected_quantity` | same, only `quality='rejected'` |
| `reject_rate` | `rejected_quantity / received_quantity` (None if 0) |

Rates are `Decimal` quantized to 2 dp. A PO counts as on-time only when it
is `received` **and** had a due date; orders received with no `expected_date`
are excluded from the on-time denominator.

## Data model

Single table `supplier_reviews`:

- `id` — UUID PK
- `clinic_id` — FK `clinics.id` (indexed; multi-tenant)
- `supplier_id` — FK `contacts.id` (indexed)
- `score` — int, `CHECK 1..5`
- `comment` — text, nullable
- `created_by` — FK `users.id`, nullable
- `created_at` / `updated_at` — timestamptz via `TimestampMixin`
- `UNIQUE (clinic_id, supplier_id)` — one current rating per supplier

The supplier FK targets `contacts.id` directly (the suite treats suppliers
as `Contact(contact_type='supplier')`); there is no `suppliers` extension
row dependency here.

## Dependencies

`manifest.depends = ["contacts", "purchase_orders"]` — imports `Contact`
(supplier identity) and `PurchaseOrder`/`PurchaseReceipt`/
`PurchaseReceiptLine` (metrics). All reads → declared deps.

## Permissions

`supplier_ratings.read`, `supplier_ratings.write`. Role grants mirror
`purchase_orders`: admin wildcard; dentist/hygienist read-only;
assistant/receptionist read+write (front-desk owns vendor ratings).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_supplier_ratings` | READ | `SupplierRatingsService.list_ratings` | `supplier_ratings.read` |
| `get_supplier_rating` | READ | `SupplierRatingsService.get_ratings` | `supplier_ratings.read` |
| `create_supplier_review` | WRITE | `SupplierRatingsService.create_review` | `supplier_ratings.write` |

All three are `exposes_free_text=True`: supplier names and comments are
free prose kept off the cloud LLM path under redaction. Metrics and ids
return as native UUID/Decimal for jsonify.

## Events emitted / consumed

None. Metrics are derived live from the purchase order ledger, so nothing
needs a `purchase_order.received` subscription.

## Lifecycle

- `installable=True`, `auto_install=False` (optional, activated from the
  admin UI), `removable=True`.
- Migration `rat_0001` on its own `supplier_ratings` Alembic branch,
  `depends_on=("con_0001",)` (the supplier FK needs `contacts` before it);
  registered in `backend/alembic.ini`.

## CHANGELOG

See `./CHANGELOG.md`.