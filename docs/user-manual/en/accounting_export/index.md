---
module: accounting_export
last_verified_commit: f70d47ff
---

# Accountant export

This optional module produces a downloadable file with the **invoices**
and **payments** of a chosen period to hand off to your accountant
(*gestoría*), without copying them by hand from the app.

The module **only exports** existing billing data — it never creates new
invoices or fiscal documents.

## Screens

- [Accountant export](./screens/accounting-export.md) — pick the period,
  preview, and download the ZIP.

## What gets exported

Only **issued invoices** and the **payments allocated to those invoices**
are exported. Payments not tied to any invoice are never included, and
the export never juxtaposes collected vs invoiced amounts.

The ZIP contains two CSV files:

- `facturas.csv` — number, series, date, customer, tax ID, base, VAT
  rate, VAT amount, total and status.
- `cobros.csv` — payment date, invoice, amount, method and reference. A
  refund appears as its own row with a **negative** amount, on the day it
  was refunded.

## Quick reference

| Action | Permission |
|--------|------------|
| View the page and preview | `accounting_export.export.read` |
| Download the export | `accounting_export.export.run` |

By default only the **admin** role holds these permissions.

## Related modules

- **Billing** — source of the invoices and their allocated payments.
- **Payments** — provides each payment's method, date and reference.
