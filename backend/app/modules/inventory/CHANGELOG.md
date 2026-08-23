# Changelog — inventory module

## Unreleased

- Initial release (issue #220): standalone stock list with low-stock alerts.
- Two tables: `inventory_categories` (per-clinic grouping) and
  `inventory_items` (stock items with quantity tracking). Own Alembic
  branch (`inventory`), chains off core `0001`.
- Atomic stock adjustment via SQL (`UPDATE … SET quantity = quantity +
  :delta WHERE quantity + :delta >= 0`) to guard against the race
  condition documented in issue #153. No application-level locking.
- Low-stock detection: dynamic query (`quantity <= min_quantity AND
  min_quantity > 0`) plus denormalized `is_low_stock` flag recomputed
  on every write.
- Soft delete (`status = 'deleted'`), never hard-delete.
- 10 REST endpoints (items CRUD, adjust-stock, low-stock, dashboard
  stats, categories CRUD) under `/api/v1/inventory/`.
- 4 agent tools: `list_inventory`, `get_inventory_item`,
  `create_inventory_item`, `adjust_stock`.
- Permissions: `inventory.read`, `inventory.write`, `inventory.delete`.
- `auto_install=False`, `removable=True`.
- Tests: HTTP-level CRUD, multi-tenancy isolation, low-stock filter,
  atomic stock adjustment (rejects negative), Alembic uninstall
  round-trip.
- Frontend Nuxt layer: item list page (`/inventory`) with category
  filter, low-stock toggle, create/edit/delete. Composable
  `useInventory.ts`, five locales (en/es/fr/pt/ta), `nuxt.config.ts`
  with all locales registered.
- `PERMISSIONS.inventory` added to `frontend/app/config/permissions.ts`.
- `nav.inventory` key in all five module locale files for sidebar nav.
- Default role_permissions: admin full access, all other roles read-only
  (clinics can widen from the module admin UI).
