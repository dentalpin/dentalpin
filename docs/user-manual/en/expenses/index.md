---
module: expenses
last_verified_commit: 3d0fc1d1
---

# Expenses

Fixed and recurring office cost tracking for the clinic: rent,
utilities, salaries, supplies, equipment, insurance, maintenance and
other. Each expense carries a date and optional description; a monthly
summary aggregates totals per category.

**Sensitive by default**: only `admin` sees the module initially (rent
and salaries are payroll-adjacent). The clinic can grant
`expenses.read` / `expenses.write` to other roles from the module admin
UI.

## Screens

- [Expense list](./screens/index.md): category filter, expense
  creation, monthly per-category totals and delete with confirmation.

## Importing from CSV

`POST /api/v1/expenses/import.csv` (multipart `file`, `expenses.write`):

```bash
curl -X POST "https://clinic/api/v1/expenses/import.csv?dry_run=false" \
  -H "Authorization: Bearer $TOKEN" -F file=@expenses.csv
```

Columns: `category*` (rent|utilities|salaries|supplies|equipment|
insurance|maintenance|other), `amount*` (decimal > 0),
`expense_date*` (YYYY-MM-DD or DD/MM/YYYY), `description`.
Delimiter `,` or `;` (auto-detected), UTF-8, max 1000 rows / 1 MiB.
Commit is all-or-nothing. Report shape: `{total, valid, created,
errors}`.
