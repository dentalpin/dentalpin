---
module: expenses
last_verified_commit: 3d0fc1d1
---

# expenses — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `expenses.read` | List, view, monthly totals | `GET /api/v1/expenses`, `GET /api/v1/expenses/monthly-totals` |
| `expenses.write` | Create, update, delete | `POST /api/v1/expenses`, `PATCH /api/v1/expenses/{id}`, `DELETE /api/v1/expenses/{id}`, `POST /api/v1/expenses/import.csv` |

Default role mapping: **admin only** — rent and salaries are sensitive,
so `role_permissions = {"admin": ["*"]}` and every other role gets
nothing out of the box. Clinics can widen it from the module admin UI.
