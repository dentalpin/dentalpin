---
module: supplier_ratings
last_verified_commit: 0f333000
---

# supplier_ratings — Events

The `supplier_ratings` module publishes **no events** and subscribes to
**no events**.

Delivery/quality metrics are computed **on demand** from the purchase
order ledger — `purchase_orders`, `purchase_receipts` and
`purchase_receipt_lines` — so there is nothing to maintain when an order
is received or cancelled. The scorecard self-corrects on the next read
because every figure is derived, not cached. The manual review rows
(`supplier_reviews`) are only ever read or written through this module's
own endpoints, so no cross-module notification is needed either.