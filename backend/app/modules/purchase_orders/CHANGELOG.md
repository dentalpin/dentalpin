# Changelog - purchase_orders module

## Unreleased

- Shared procurement frontend (suite #227): one Nuxt layer owned here
  with five pages (suppliers, vendor items, orders, reorder, ratings),
  `useProcurement` composable, `en`/`es` locales, nav entries in the
  manifest and suite groups in `frontend/app/config/permissions.ts`.
  Screen docs under `docs/user-manual/{en,es}/procurement/`.
- Review fixes: rejected units no longer count towards `quantity_received`
  (the line stays open for the replacement); PDF shows supplier name and
  PO reference and escapes user text; agent tools no longer read a
  `user_id` that `AgentContext` does not carry; `received_at` is tz-aware.

- Initial module (roadmap issue #227-3): procurement purchase orders with
  a full lifecycle (`draft -> sent -> confirmed -> received|cancelled`) and
  batch receiving.
- Added `PurchaseOrder`, `PurchaseOrderLine`, `PurchaseReceipt`,
  `PurchaseReceiptLine` models. `UNIQUE (purchase_order_id,
  inventory_item_id)` on lines (one order can't repeat an item).
- Service layer (`PurchaseOrderService`): clinic-scoped supplier/item
  validation at creation, duplicate-item guard, explicit status
  transitions with an allowed-matrix (409 on invalid moves), batch
  receiving where only `good` lines move stock (via
  `InventoryService.apply_movement`, `reason='purchase_receipt'`,
  idempotent per receipt), over-receipt guard, auto-stamp of
  `received_at` when every line fulfils, and a lock on editing received
  orders.
- Batch receive is one transaction: receipt rows, good-line stock
  movements and the auto-transition commit or roll back together
  (ADR 0019).
- Self-contained WeasyPrint PDF export (`GET /purchase_orders/{id}/pdf`,
  en/es labels, clinic currency, DRAFT watermark for draft orders).
- RBAC mirrors `suppliers`: admin wildcard; dentist/hygienist
  read-only; assistant/receptionist read+write.
- Agent tools exposed: `list_purchase_orders`, `get_purchase_order`,
  `create_purchase_order`, `transition_purchase_order`,
  `receive_purchase_order` (wrapping service methods), all
  `exposes_free_text=True`.
- Events published: `purchase_order.created`,
  `purchase_order.status_changed`, `purchase_order.received`
  (transactional per ADR 0019; `EventType` additions in
  `app/core/events/types.py`).
- Migration `po_0001_initial` on own Alembic branch (`purchase_orders`),
  depending on `contacts@con_0001` + `inventory@inv_0002`.
- `removable=True` - supports full uninstall with roundtrip tests.
- Registered `app/modules/purchase_orders` in `backend/alembic.ini`
  `version_locations` so the Alembic CLI graph (heads/upgrade) resolves
  `po_0001` (CI parity).

## Follow-up

- PO-line `unit_price` is a manual snapshot, independent of
  `supplier_items` (#227-2) per-vendor pricing. Once #227-2 merges, source
  the per-vendor unit price from the supplier-item link automatically
  (`supplier_id` + `inventory_item_id`) in `PurchaseOrderService.create_order`,
  keeping the manual snapshot as fallback. No migration needed
  (`unit_price` already exists on `purchase_order_lines`).