# Expenses module

Fixed/recurring office expense tracking (rent, utilities, salaries, supplies,
equipment, insurance, maintenance, other). Custom clinic module — standalone,
no dependency on any other module.

## Public API

Routes mounted at `/api/v1/expenses/`.

- `GET    /expenses`                  — list, filterable by category/date range; `expenses.read`
- `GET    /expenses/monthly-totals`   — totals per category for a given year+month; `expenses.read`
- `POST   /expenses`                  — create; `expenses.write`
- `PATCH  /expenses/{id}`             — edit; `expenses.write`
- `DELETE /expenses/{id}`             — delete; `expenses.write`

## Dependencies

`manifest.depends = []` — standalone.

## Permissions

`expenses.read`, `expenses.write`. Default role grants: admin full access,
all other roles (dentist, hygienist, assistant, receptionist) read-only.
Adjust `role_permissions` in `__init__.py` to change this.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_expenses` | READ | `ExpenseService.list_expenses` | `expenses.read` |
| `create_expense` | WRITE | `ExpenseService.create_expense` | `expenses.write` |
| `expense_monthly_totals` | READ | `ExpenseService.monthly_totals_by_category` | `expenses.read` |

## Events emitted

None.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- Migrations on the `expenses` Alembic branch, chained directly off the
  core `0001` migration (no cross-module foreign keys).

## CHANGELOG

See `./CHANGELOG.md`.
