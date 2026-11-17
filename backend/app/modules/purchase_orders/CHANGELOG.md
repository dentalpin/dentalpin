# Changelog - purchase_orders module

## Unreleased

- fix(#892): `GET /{order_id}/receipts/{receipt_id}` returns 404 for a receipt of another order. It checked only that the order existed and then loaded the receipt by id.
- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- fix(#705): the order PDF footer stamped the server's clock
  (`datetime.now()`); it now uses the clinic timezone like billing's.
- fix(#679): `PO_STATUSES` is derived from a new `PurchaseOrderStatus`
  Literal (one vocabulary, two shapes, no drift), and the agent tools are
  typed with it: `list_purchase_orders.order_status` rejects an unknown
  status by name instead of answering an empty page, and
  `transition_purchase_order.status` advertises the four reachable targets
  — `received` is excluded, since it is stamped only by a receive batch
  that fulfils every line.
- fix(#677): the tool parameters `order_id`, `supplier_id`, `line_item_ids`
  and `line_ids` are typed `UUID`, and `expected_date` is typed `date`,
  instead of `str`.
  The tool schema now advertises `format: uuid`, and a malformed id is
  rejected by `tool_registry.call`'s validation step naming the parameter,
  rather than reaching the handler and raising `badly formed hexadecimal
  UUID string`, which named nothing.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer; Hindi purchase-order PDF labels.
- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- feat(i18n): Telugu (`te`) purchase-order PDF labels.
- feat(#509): the purchase-order PDF for `pt-BR` reuses the `pt` labels.

- Follow-up: single error toast on the procurement pages — the
  composable passes `errorToast: false` on every call the pages
  already surface themselves, including `listSuppliers` /
  `listInventoryItems`: the option-picker loaders (`loadOptions`)
  catch and toast instead of swallowing (review round 2).
- fix(#485): the order PDF renders its own labels in all ten host
  locales, the route accepts the shared `PDF_LOCALE_PATTERN` instead of
  `es|en`, amounts follow `LOCALE_BY_LANG` (a German order printed
  `1,234.56` next to an invoice printing `1.234,56`), and Arabic
  mirrors the document.
- feat(#232): sidebar entries grouped under the Inventory header (`nav.section` "inventory").
- feat(i18n): full locale set for the shared procurement frontend
  (fr, de, pl, it, ta, hu, ar, pt alongside en/es).
- Shared procurement frontend (suite #227): one Nuxt layer owned here
  with five pages (suppliers, vendor items, orders, reorder, ratings),
  `useProcurement` composable, `en`/`es` locales, nav entries in the
  manifest and suite groups in `frontend/app/config/permissions.ts`.
  Screen docs under `docs/user-manual/{en,es}/purchase_orders/`.
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