# Changelog — expenses module

## Unreleased

- feat(#131): German (de) locale for the module's frontend layer.

- Mark `list_expenses` / `create_expense` tools `exposes_free_text=True`:
  the user-entered `description` is free prose and must stay off the
  cloud LLM path under redaction.

## 0.1.0 — initial release

- Fixed/recurring office expense CRUD with clinic scoping, category
  filter, date-range filters, pagination, and a monthly
  totals-by-category summary.
- Searchable sidebar entry (`nav.expenses`) gated on `expenses.read`.
- Agent tools: `list_expenses`, `create_expense`,
  `expense_monthly_totals`.
- `auto_install=False`, `removable=True`, own Alembic branch, uninstall
  round-trip + tenant-isolation + HTTP date-filter tests.
- Admin-only role permissions by default (sensitive data); clinics can
  widen from the module admin UI.
- Docs: technical overview/permissions/events pages, user manual en+es.

