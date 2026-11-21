# Accounting export module

Optional, removable, **model-free** module that exports billing data for
the clinic's accountant (*gestoría*). Generates a downloadable ZIP with
`facturas.csv` + `cobros.csv` for a chosen period. Issue #73.

## Public API

Routes mounted at `/api/v1/accounting_export/`.

| Method | Path       | Permission                       |
|--------|------------|----------------------------------|
| GET    | `/preview` | `accounting_export.export.read`  |
| GET    | `/run`     | `accounting_export.export.run`   |

`/preview` returns counts, totals and a 10-row sample of each dataset.
`/run` streams a ZIP (`separator` query param `,`/`;` — `;` uses comma
decimals for Excel-ES).

## Dependencies

`manifest.depends = ["billing", "payments"]`. Data is read **only** via
`InvoiceService.list_for_export` (billing's service API). No model
imports from billing/payments, no FKs, no own tables.

## Permissions

`export.read`, `export.run`. Admin-only by default (`role_permissions`
grants `admin: ["*"]` and no other role).

## Tools exposed

None (`get_tools()` → `[]`). This is a UI-driven file export; nothing to
expose to the agent.

## Off-books boundary (critical)

**Invoice-centric.** Only issued invoices and the payments **allocated to
them** (`InvoicePayment`) are exported. The raw `Payment` ledger is never
surfaced and the export never juxtaposes the collection axis against the
invoice axis — see ADR 0010 and the payments module gotchas. A cash
payment not tied to any invoice does not appear. Drafts are excluded
(not fiscal documents).

## Lifecycle

- `installable=True`, `auto_install=False` (activated from admin UI),
  `removable=True`.
- Model-free → owns no tables. Carries an empty isolated Alembic branch
  (`accexp_0001`, no-op) only to satisfy the removable-branch invariant
  (ADR 0002). Uninstall never touches the schema; round-trip is trivial.

## Gotchas

- **No new dependencies.** CSV via stdlib `csv`, bundle via stdlib
  `zipfile`. XLSX/ContaPlus/A3 are deliberate follow-ups.
- **Verifactu data is out.** Verifactu is optional and can't go in
  `depends`. If an "AEAT state" column is ever wanted, read it from
  `Invoice.compliance_data['ES']` (a billing-owned field) — no new
  dependency.
- **Taxable base** is `subtotal - total_discount`, not `subtotal`.
- **Refunds are negative `cobros.csv` rows** (#988). Billing never edits
  `InvoicePayment` on a refund, it nets refunds at read time in proportion
  to each allocation's share of the payment; `payment_rows` does the same
  and dates the row on the clinic's day of `refunded_at` (the router passes
  the clinic zone). Still keyed to the invoice period like every cobro.
- **VAT rate** column shows the single item rate, or `varios` when the
  invoice mixes rates.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0010-payments-as-primitive-module.md`

## CHANGELOG

See `./CHANGELOG.md`.
