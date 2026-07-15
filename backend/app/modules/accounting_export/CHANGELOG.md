# Changelog — accounting_export module

## Unreleased

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
