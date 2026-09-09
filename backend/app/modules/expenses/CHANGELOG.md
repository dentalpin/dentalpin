# Changelog — expenses module

## Unreleased

- fix(#431 review): all-or-nothing bulk commit for CSV import;
  `,`/`;` sniffing + DD/MM/YYYY dates; bounded upload reads; CSV
  agent tool dropped (HTTP-only).
- feat: CSV expense import — `POST /expenses/import.csv` (dry-run default,
  commit with `dry_run=false`). Validation
  reuses `ExpenseCreate`; unknown columns ignored, 1000 rows / 1 MiB caps.

- feat(#334): Hungarian (hu) locale for the module's frontend layer.

- feat(i18n): Arabic (ar) locale for the module's frontend layer.

- feat(#131): German (de) locale for the module's frontend layer.
- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

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

