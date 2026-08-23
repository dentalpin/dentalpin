# Inventory module

Owns clinic stock tracking: item catalog with quantities, categories, low-stock alerts, and atomic stock adjustments.

## Public API

- Routes mounted at `/api/v1/inventory/`.
- Key endpoints:
  - `GET    /inventory/`                — list items; permission `inventory.read`
  - `POST   /inventory/`                — create item; permission `inventory.write`
  - `GET    /inventory/{id}`            — get item detail; permission `inventory.read`
  - `PATCH  /inventory/{id}`            — update item; permission `inventory.write`
  - `DELETE /inventory/{id}`            — soft-delete item; permission `inventory.delete`
  - `POST   /inventory/{id}/adjust-stock` — atomic stock adjustment; permission `inventory.write`
  - `GET    /inventory/low-stock`       — low-stock items; permission `inventory.read`
  - `GET    /inventory/stats/dashboard` — stock summary; permission `inventory.read`
  - `GET    /inventory/categories`      — list categories; permission `inventory.read`
  - `POST   /inventory/categories`      — create category; permission `inventory.write`
  - `GET    /inventory/categories/{id}` — get category; permission `inventory.read`
  - `PATCH  /inventory/categories/{id}` — update category; permission `inventory.write`

## Dependencies

`manifest.depends = []`. No cross-module dependencies.

## Frontend

Nuxt layer at `frontend/` with:
- **Page:** `/inventory` — item list with category filter, low-stock toggle, create/edit/delete actions
- **Composable:** `useInventory.ts` — typed API client for all endpoints
- **Locales:** en, es, fr, pt, ta (all five, matching repo convention)
- **Config:** `PERMISSIONS.inventory` in `frontend/app/config/permissions.ts`

## Permissions

`inventory.read`, `inventory.write`, `inventory.delete`

(Mirror `get_permissions()`. Roles → permissions live in the manifest.)

Default role mapping: admin has full access, all other roles are read-only. Clinics can widen via the module admin UI.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_inventory` | READ | `InventoryItemService.list` | `inventory.read` |
| `get_inventory_item` | READ | `InventoryItemService.get` | `inventory.read` |
| `create_inventory_item` | WRITE | `InventoryItemService.create` | `inventory.write` |
| `adjust_stock` | WRITE | `InventoryItemService.adjust_stock` | `inventory.write` |

## Events emitted

| Event | When | Payload keys |
|---|---|---|
| *(none yet)* | V1 is standalone | — |

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| *(none)* | — | — |

## Lifecycle

- `installable` / `auto_install=False` / `removable=True` from manifest.
- Removable: own Alembic branch (`inventory`); uninstall downgrades only `inv_0001`.

## Gotchas / non-obvious invariants

- Every query MUST filter by `clinic_id`, including inside agent tool handlers.
- Stock adjustments use atomic SQL (`UPDATE … WHERE quantity + :delta >= 0`) to prevent the race condition from #153 — do NOT lock in application code.
- `is_low_stock` is recomputed on every update/adjust to keep it consistent.
- Items are soft-deleted (`status=deleted`), never hard-deleted.
- `inventory_categories` has a unique constraint on `(clinic_id, name)`.

## CHANGELOG

See `./CHANGELOG.md`.
