# Changelog — expenses module

## Unreleased

- fix(#1114): CSV import no longer answers 500 on a row with more cells than the header (extra cells are ignored), and reads a column whose header has surrounding spaces.

- fix(#962): the CSV import reads thousands separators in both conventions (`1,200`, `1.200`, `1,234.56`, `1.234,56`). `1,200` and `1.200` used to be imported as 1.20, valid and silent, so the expense was stored 1000 times too small; `1,234.56` and `1.234,56` were refused.
- fix(#976): `PATCH` with `null` for `category`, `amount` or `expense_date` is a 422 (was a 500 from the NOT NULL column).
- fix(#974): an unreadable `expense_date` in the CSV import is a row error. It raised `CsvImportError`, so one bad date rejected the whole file and the dry run never listed the other rows.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer.

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- fix(#522): the `expense_date` default read the UTC day, so a clinic east of
  UTC filing an expense before its offset had elapsed got yesterday's date
  pre-filled. Now uses `toISODate`.

- feat(#232): sidebar entry grouped under the Financials header (`nav.section` "financials").
- fix(#431 review): CSV `amount` accepts the decimal comma (`1200,50`),
  matching the `;` sniffing for Spanish Excel exports.
- fix(#431 review round 3): oversize-upload 422 test mirrored from
  patients (expenses `read_upload_limited` path now covered).
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

