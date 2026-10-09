# Changelog — accounting_export module

## Unreleased

- test(#552): branch-scoped uninstall round-trip test (heads, branch downgrade, reinstall).

- fix(#611): party names and descriptions in `facturas.csv` / `cobros.csv`
  are neutralised against spreadsheet formula injection before the file
  reaches the accountant. Decimal amounts keep their own formatting path,
  so a credit note stays a negative number rather than becoming text.

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- fix(#522): every date preset (`currentMonth`, `previousMonth`,
  `currentQuarter`, `previousQuarter`, `yearToDate`) built its bounds from a
  local midnight and rendered them with `toISOString()`, i.e. in UTC — so a
  clinic anywhere east of UTC exported a window starting and ending one day
  early. `previousMonth` is the default preset, so the wrong range was the
  one selected on arrival. Now uses `toISODate`.

- feat(#232): sidebar entry grouped under the Financials header (`nav.section` "financials").
- feat(#334): Hungarian (hu) locale for the module's frontend layer.

- feat(i18n): Arabic (ar) locale for the module's frontend layer.
- feat(i18n): the frontend layer's directional spacing, borders, text alignment and inset positioning now resolve against the document direction (physical→logical CSS utilities, Arabic RTL support).

- feat(#131): German (de) locale for the module's frontend layer.
- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

- i18n: add Tamil locale (`ta.json`) with full UI coverage.

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- i18n: add Portuguese locale (`pt.json`) with full UI coverage.

- i18n: add French locale (`fr.json`) with full UI coverage.

- Initial release. Optional, removable, model-free module that exports
  billing data for the accountant (*gestoría*) — issue #73.
- Endpoints `GET /preview` (counts + totals + sample) and `GET /run`
  (ZIP with `facturas.csv` + `cobros.csv`). Admin-only.
- Invoice-centric: only issued invoices and their allocated payments are
  exported; the raw payment ledger and the paid-vs-invoiced diff are
  never surfaced (off-books boundary, ADR 0010).
- CSV via stdlib `csv` (configurable `,`/`;` separator, comma decimals +
  UTF-8 BOM for Excel-ES), bundle via stdlib `zipfile`. No new deps.
- Reads data via `InvoiceService.list_for_export` only; no model imports.
