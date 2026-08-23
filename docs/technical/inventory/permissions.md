# Inventory module — permissions

## Permission strings

| Permission | Scope | Endpoints |
|------------|-------|-----------|
| `inventory.read` | Read access | `GET /inventory/`, `GET /inventory/{id}`, `GET /inventory/low-stock`, `GET /inventory/stats/dashboard`, `GET /inventory/categories`, `GET /inventory/categories/{id}` |
| `inventory.write` | Create and update | `POST /inventory/`, `PATCH /inventory/{id}`, `POST /inventory/{id}/adjust-stock`, `POST /inventory/categories`, `PATCH /inventory/categories/{id}` |
| `inventory.delete` | Soft-delete items | `DELETE /inventory/{id}` |

## Role → permission mapping

| Role | Permissions |
|------|-------------|
| admin | `*` (all) |
| dentist | `read` |
| hygienist | `read` |
| assistant | `read` |
| receptionist | `read` |

Default is restrictive: only admin can create, update, delete, or adjust stock. Clinics can widen via the module admin UI.

## Notes

- Permissions are returned from `get_permissions()` without the module prefix; the registry namespaces them automatically as `inventory.read`, etc.
- Frontend gating uses `PERMISSIONS.inventory.read`, `PERMISSIONS.inventory.write`, `PERMISSIONS.inventory.delete` from `frontend/app/config/permissions.ts`.
