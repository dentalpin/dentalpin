---
module: purchase_orders
last_verified_commit: 8b8e9375
---

# purchase_orders — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

All three are published inside the same transaction as the change (ADR
0019), so transactional subscribers see the uncommitted row and roll back
with it.

| Event | Payload |
|-------|---------|
| `purchase_order.created` | `(clinic_id, order_id, supplier_id, status)` |
| `purchase_order.status_changed` | `(clinic_id, order_id, supplier_id, from_status, status)` |
| `purchase_order.received` | `(clinic_id, order_id, supplier_id, receipt_id, applied[{inventory_item_id, quantity}], fully_received)` |

No bundled subscriber today. `inventory_reorder` (#227-4) is expected to
subscribe to `purchase_order.received` to clear open replenishment
suggestions; `supplier_ratings` (#227-5) is the venue for quality
deductions derived from `applied`/quality.

## Subscribed

_This module does not subscribe to any events._

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, inside the transaction after the change.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.