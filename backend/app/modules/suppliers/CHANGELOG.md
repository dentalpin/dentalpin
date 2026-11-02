# Changelog — suppliers module

## Unreleased

- fix(#740): clearing a supplier's lead time saves it as empty. The cleared input sent `""`, which the `int` field answered with 422.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- fix(#677): the `get_supplier` / `update_supplier` tool parameter
  `supplier_id` is typed `UUID` instead of `str`.
  The tool schema now advertises `format: uuid`, and a malformed id is
  rejected by `tool_registry.call`'s validation step naming the parameter,
  rather than reaching the handler and raising `badly formed hexadecimal
  UUID string`, which named nothing.

- Initial module (roadmap issue #227-1): procurement vendor directory as a
  1:1 extension on top of `contacts` (`contact_type='supplier'`).
- Added `Supplier` model with sourcing-specific fields: `website`,
  `payment_terms`, `lead_time_days`, `is_preferred`.
- Service layer provides atomic CRUD for the `Contact + Supplier` row pairing,
  ensuring both are created/updated together in a single transaction.
- RBAC identical to `contacts`: admin wildcard; dentist/hygienist read-only;
  assistant/receptionist read+write (front-desk procurement management).
- Agent tools exposed: `list_suppliers`, `get_supplier`, `create_supplier`,
  `update_supplier` (wrapping `SupplierService` methods).
- Migration `supp_0001_initial` on own Alembic branch (`suppliers`),
  depending on `contacts@con_0001`.
- `removable=True` — supports full uninstall with roundtrip tests.
- Registered `app/modules/suppliers` in `backend/alembic.ini` `version_locations`
  so the Alembic CLI graph (heads/upgrade) resolves `supp_0001` (CI parity).
- Registered `suppliers` in `pyproject.toml` module entry points so the module
  is discoverable in production (`DENTALPIN_DEV_MODULE_SCAN=False`); closes the
  entry-point parity gap reported by `tests/test_entry_point_parity.py`.
