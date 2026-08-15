# Billing module

Invoices, payments, credit notes, PDF generation.

## Public API

Routes mounted at `/api/v1/billing/`.

## Dependencies

`manifest.depends = ["patients", "catalog", "budget"]`.

## Permissions

`billing.read`, `billing.write`, `billing.admin`.

## Tools exposed

Agent tools in `tools.py` — **READ ONLY** (no issuing/voiding: invoice
emission stays manual; Veri*Factu chaining is irreversible).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_invoices` | READ | `InvoiceService.list_invoices` | `billing.read` |
| `get_invoice` | READ | `InvoiceService.get_invoice(include_payments=False)` | `billing.read` |

**Off-books boundary.** Invoice axis only: no paid/pending amounts, no
payments join — `get_invoice` is hard-wired to
`include_payments=False` so the two axes can't be juxtaposed. Enforced
by tests in `tests/test_module_tools.py`.

## Events emitted

- `invoice.issued`
- `invoice.sent`
- `invoice.paid`

## Events consumed

- _none today_. The legacy ``budget.completed`` subscription was
  removed in 2026-04 — that event was never actually published, so
  the handler was orphaned. Re-add a subscription here when invoices
  need to react to budget lifecycle events again.

## Lifecycle

- `removable=False`. Fiscal data has legal retention (see verifactu
  module for AEAT specifics).

## Gotchas

- **Compliance hooks live in compliance modules**, not here. The
  `verifactu` module attaches via `BillingComplianceHook` on
  `invoice.issued` to chain into AEAT. Don't import verifactu from
  billing — the relation is via hooks + events.
- **PDF generation uses WeasyPrint** (`pdf.py`). Requires the system
  fonts present in the production image.
- **Quote discounts are always folded into invoice lines.**
  `create_from_budget` stores the line discount + the prorated global
  discount share (`budget.pricing.allocate_global_discount`) on each
  `InvoiceItem` — absolute (prorated by invoiced quantity) unless a
  percentage line discount is the only discount. Never add an
  invoice-level discount: Verifactu derives `BaseImponible` per line
  from `line_subtotal - line_discount` and `ImporteTotal` from
  `invoice.total`; a header discount would desync the AEAT record
  (issue #167). The from-budget wizard mirrors this via
  `items[].global_discount_share` from the budget API.
- **Credit notes** are issued via the same workflow as invoices,
  flagged via the document type. Don't introduce a parallel pipeline.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
