---
module: inventory_reorder
last_verified_commit: 0f333000
---

# inventory_reorder — Events

The `inventory_reorder` module publishes **no events** and subscribes to
**no events**.

Suggestions are computed **on demand** from live state — the movement
ledger, supplier sourcing and open purchase orders — so there is nothing
to clear when a purchase order is received or cancelled. The reorder
policy deliberately does **not** subscribe to `purchase_order.received`
(contrary to an older note in `purchase_orders/events.md`); the
suggestion set self-corrects on the next `/suggestions` or
`/orders` call because `on_order` and `stock_quantity` are derived, not
cached.

The `purchase_order.created` event is still published when `POST
/orders` creates draft POs — but by `purchase_orders` itself (through
`PurchaseOrderService.create_order`), inside the same transaction
(ADR 0019). `inventory_reorder` adds no event of its own on top of it.