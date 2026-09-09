# Expenses module

Fixed/recurring office expense tracking (rent, utilities, salaries, supplies,
equipment, insurance, maintenance, other). Custom clinic module — standalone,
no dependency on any other module.

## Public API

Routes mounted at `/api/v1/expenses/`.

- `GET    /expenses`                  — list, filterable by category/date range; `expenses.read`
- `GET    /expenses/monthly-totals`   — totals per category for a given year+month; `expenses.read`
- `POST   /expenses`                  — create; `expenses.write`
- `POST   /expenses/import.csv`        — CSV import (dry-run default,
  `dry_run=false` commits); `expenses.write`
- `PATCH  /expenses/{id}`             — edit; `expenses.write`
- `DELETE /expenses/{id}`             — delete; `expenses.write`

## Dependencies

`manifest.depends = []` — standalone.

## Permissions

`expenses.read`, `expenses.write`. Default role grants: **admin only** —
rent and salaries are sensitive, so no other role sees the module out of
the box. Clinics can widen `role_permissions` in `__init__.py` (or from
the module admin UI) if e.g. reception should record supplies.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_expenses` | READ | `ExpenseService.list_expenses` | `expenses.read` |
| `create_expense` | WRITE | `ExpenseService.create_expense` | `expenses.write` |
| `expense_monthly_totals` | READ | `ExpenseService.monthly_totals_by_category` | `expenses.read` |

CSV import is HTTP-only (no agent tool — same PII-volume reason as
patients).

`list_expenses` and `create_expense` return the user-entered `description`
(free prose, may name employees) and are marked `exposes_free_text=True`,
so they are excluded from the cloud LLM path under redaction.
`expense_monthly_totals` returns only categories and totals and stays
cloud-eligible.

## Events emitted

None.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=False` (ships inactive, activated
  from the module admin UI), `removable=True`.
- Migrations on the `expenses` Alembic branch, chained directly off the
  core `0001` migration (no cross-module foreign keys).
- `tests/modules/expenses/test_uninstall_roundtrip.py` covers the
  branch-scoped downgrade/upgrade round trip required for
  `removable=True` modules.

## CHANGELOG

See `./CHANGELOG.md`.
