# Accounting export (`accounting_export`)

Optional, removable module that exports billing data for the clinic's
accountant (*gestoría*). Issue #73.

## What it does

Generates a downloadable ZIP for a chosen period (`facturas.csv` +
`cobros.csv`) so an admin can hand bookkeeping data to their accountant
without copy-pasting from the UI.

## Scope decisions

- **Invoice-centric, not a payment ledger.** Only issued invoices and the
  payments **allocated to them** are exported. The raw `Payment` table and
  the paid-vs-invoiced diff are never surfaced — this honours the
  off-books boundary documented in [ADR 0010](../adr/0010-payments-as-primitive-module.md).
- **CSV only (phase 1).** Stdlib `csv` + `zipfile`, zero new dependencies.
  XLSX, ContaPlus/A3CON diary entries and per-invoice FacturaE are
  follow-ups.
- **Stateless.** No models, no export history. Carries an empty isolated
  Alembic branch (no-op) only to satisfy the removable-branch invariant;
  uninstall never touches the schema.

## API

Mounted at `/api/v1/accounting_export/`.

| Method | Path       | Permission                      | Returns |
|--------|------------|---------------------------------|---------|
| GET    | `/preview` | `accounting_export.export.read` | Counts, totals, 10-row sample |
| GET    | `/run`     | `accounting_export.export.run`  | ZIP (`facturas.csv` + `cobros.csv`) |

Query params: `date_from`, `date_to` (ISO dates), `status` (repeatable,
whitelisted to non-draft), and on `/run` a `separator` of `,` or `;`
(`;` → comma decimals + UTF-8 BOM for Excel-ES).

### Columns

`facturas.csv`: numero, serie, fecha_emision, cliente, nif, base,
tipo_iva, cuota_iva, total, estado. `base` is `subtotal - total_discount`;
`tipo_iva` is the single item rate or `varios` when mixed.

`cobros.csv`: fecha_pago, factura, importe, metodo, referencia (one row
per invoice↔payment allocation, then one **negative** row per refund of
that payment for the invoice's share, dated on the clinic's day of the
refund — #988).

## Dependencies

`depends = ["billing", "payments"]`. Reads only via
`InvoiceService.list_for_export` — no model imports, no FKs, no own tables.

## Permissions

`export.read`, `export.run`. Admin-only by default.

## Verifactu

Out of scope. Verifactu is itself optional and can't be a hard dependency.
If an "AEAT state" column is ever wanted it can be read from
`Invoice.compliance_data['ES']` (a billing-owned field) without adding a
dependency.
