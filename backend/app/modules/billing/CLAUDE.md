# Billing module

Invoices, payments, credit notes, PDF generation.

## Public API

Routes mounted at `/api/v1/billing/`.

## Dependencies

`manifest.depends = ["patients", "catalog", "budget", "payments"]`
(billing → payments only; see ADR 0010).

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

| Event | Handler | Mode | Effect |
|---|---|---|---|
| `payment.allocated` | `events.py:on_payment_allocated` | transactional (ADR 0019) | `payment_bridge.reconcile_payment` — mirror the payment's budget allocations onto `invoice_payments` of that budget's open invoices (FIFO, preferred invoice first via `context.prefer_invoice_id`), unlink LIFO on reallocation, recompute status. Issue #178. |
| `payment.refunded` | `events.py:on_payment_refunded` | transactional | Recompute status of invoices linked to the refunded payment. |
| `clinic.created` | `events.py:on_clinic_created` | own session (published after setup commits) | Default `FAC` / `RECT` series. |

The legacy ``budget.completed`` subscription was removed in 2026-04 —
that event was never published.

## Lifecycle

- `removable=False`. Fiscal data has legal retention (see verifactu
  module for AEAT specifics).

## Gotchas

- **A series prefix is unique per clinic, not per series type.**
  `uq_invoice_series_clinic_prefix` covers `(clinic_id, prefix)`, so a
  credit-note series cannot borrow an invoice series' prefix. Both
  `POST /series` and `PUT /series/{id}` catch the `IntegrityError` and
  return **409** rather than pre-checking with a SELECT — a
  select-then-insert leaves a window where two concurrent creates both
  pass. It is the table's only unique constraint, which is what makes
  labelling the violation safe.

- **GDPR erasure retains the invoice's fiscal snapshot.**
  `erasure.BillingErasureContributor` owns the `billing` coverage scope
  (ADR 0038, #657) and writes nothing: an issued document must stay as
  issued, and an e-invoice already registered with the tax authority
  cannot be altered at all (Art. 17(3)(b)). It declares `email`
  (`billing_email`) and `identity` (`billing_tax_id`, the patient's
  NIF/CIF); `phone` is not held here. Adding a patient contact column to
  the snapshot means updating that declaration.

- **`BudgetItem.invoiced_quantity` is a derived cache, never a
  counter.** `service.resync_invoiced_quantities` recomputes it from the
  live `invoice_items` (credit-note lines subtract, deleted/voided
  documents don't count). Call it after any mutation of a line carrying
  `budget_item_id` — `create_from_budget`, void/delete, item edits and
  credit notes already do. Never `+=`/`-=` it by hand (issue #175).
- **"Today" is the clinic's, never the server's.** The server runs on
  UTC; an invoice's default `issue_date` and the year in its number come
  from `clinic_today(ctx.clinic.timezone)` (`app/core/utils/dates.py`),
  passed into `issue_invoice(today=…)` and on to `generate_number`. Keep
  the two on the same value — the number embeds the year.
- **The sequential is unique per (series, fiscal year), not per
  series.** A `reset_yearly` series (the default) restarts at 1 each
  year; `generate_number` returns the year it drew in and the workflow
  stores it on `Invoice.fiscal_year`. The backstop index is
  `(series_id, fiscal_year, sequential_number)` `NULLS NOT DISTINCT`
  (`bil_0006`, #689). Anything that writes `sequential_number` must write
  `fiscal_year` with it; anything that groups sequentials by year
  (the gap report) reads `fiscal_year`.
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
- **Budget ↔ invoice bridge (`payment_bridge.py`, issue #178).** One
  rule: money allocated to a budget is money for that budget's
  invoices. Three entry points, all in-tx: the `payment.allocated`
  subscriber, `issue_invoice` (sweeps anticipos already collected on
  the quote into the fresh invoice — it may be born `paid`), and the
  orchestrator `POST /invoices/{id}/payments` (allocates to
  `invoice.budget_id` when set, `on_account` + explicit link for manual
  invoices). `reconcile_payment` is idempotent (objective − current);
  never write `invoice_payments` for a from-budget invoice anywhere
  else. Lock order is **budget row → invoice rows** (`lock_budget`).
- **`compute_paid_summary` is the only paid arithmetic.** Refunds are
  subtracted proportionally there; any other surface (reports' patient
  summary, lists) must reuse it / `compute_paid_summaries_for_invoices`
  instead of summing `invoice_payments.amount` raw.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0010-payments-as-primitive-module.md`
- `docs/adr/0019-transactional-event-handlers.md`

## CHANGELOG

See `./CHANGELOG.md`.

## Billing party on drafts

Drafts store no billing data. `InvoiceWorkflowService.issue` snapshots `Patient.effective_billing_name` / `effective_billing_tax_id` (explicit billing fields, else patient name and DNI/NIE — never a passport). `has_complete_billing_info` is the same rule, so the UI warning and the issue gate agree (modulo the country hook waiver). The from-budget wizard reads `POST /api/v1/payments/summary/by-budgets` to hide payment terms on fully collected budgets (`payments` is in `depends`).
