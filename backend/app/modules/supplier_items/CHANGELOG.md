# Changelog - supplier_items module

## Unreleased

- Initial module (roadmap issue #227-2): supplier <-> inventory item link
  table supporting the "multiple vendors per item" model.
- Added `SupplierItem` model: `supplier_id`, `inventory_item_id`,
  `supplier_sku`, `price` (`Numeric(12, 2)`), `is_active` (soft delete),
  with a UNIQUE `(supplier_id, inventory_item_id)` constraint (one price
  per pair).
- Service layer (`SupplierItemService`): clinic-scoped validation on both
  ends of the link at creation, list filters by supplier/item, 409 on
  duplicate pairs (from the UNIQUE constraint, L6), **soft delete** (L7:
  `deactivate_link` sets `is_active=false` so historical purchase-order
  references stay valid — no hard DELETE).
- `update_link` forwards only supplied fields (`exclude_unset`, M4) so an
  omitted price/SKU is not silently wiped.
- Responses denormalize `supplier_name` and `item_name` via joins for
  readable lists.
- RBAC mirrors `suppliers`/`contacts`: admin wildcard; dentist/hygienist
  read-only; assistant/receptionist read+write.
- Agent tools exposed: `list_supplier_items`, `get_supplier_item`,
  `create_supplier_item`, `update_supplier_item` (wrapping
  `SupplierItemService` methods), all `exposes_free_text=True`.
  `update_supplier_item` forwards only the fields the agent set (M4).
- Migration `sui_0001_initial` on own Alembic branch (`supplier_items`),
  depending on `suppliers@supp_0001` + `inventory@inv_0002`.
- `removable=True` - supports full uninstall with roundtrip tests.
- Registered `app/modules/supplier_items` in `backend/alembic.ini`
  `version_locations` so the Alembic CLI graph (heads/upgrade) resolves
  `sui_0001` (CI parity), and as a `dentalpin.modules` entry point in
  `backend/pyproject.toml` (production loader parity).
- Review fixes: `create_link` validates the `suppliers` row (FK target)
  rather than only the Contact, and revives a soft-deleted row for the same
  pair instead of returning 409 — a deactivated pair can be linked again.
