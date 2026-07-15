# Changelog — billing module

## Unreleased

- i18n: add `fr` fallback to invoice description resolution in
  service layer so French-localized treatment names appear on invoices.

- fix(security): lock the invoice row `FOR UPDATE` on the payment and
  issue endpoints (audit S3/C2 + C4, #97). Two concurrent payments could
  both read the full `balance_due` and over-collect past the total; two
  concurrent issues of one draft could both pass the draft-only guard,
  burning a sequential number and chaining a duplicate AEAT record. The
  issue path also refreshes `status` under the lock so the second caller
  sees `issued`. Guard tests in `test_issue_and_payment_guards`.

- fix(migrations): add the invoice-number uniqueness backstop that the
  `Invoice` model comment already claimed existed (audit S3/C3, #93).
  New migration `bil_0005` creates two partial unique indexes —
  `ix_invoices_clinic_number_unique` on `(clinic_id, invoice_number)`
  and `ix_invoices_series_sequential_unique` on
  `(series_id, sequential_number)`, both `WHERE … IS NOT NULL` so drafts
  don't collide. Duplicate fiscal numbers are now rejected at the DB
  level, not just by the (serialized) generator. Model `__table_args__`
  updated to declare the indexes; misleading comment removed.

- feat(service): add `InvoiceService.list_for_export(clinic_id, date_from,
  date_to, statuses)` — non-paginated read returning non-draft invoices
  with items + allocated payments eager-loaded, for the new
  `accounting_export` module's gestoría hand-off. Read-only API on
  billing's own data; consumers never import billing models.

- feat(agents): expose `tools.py` for the copilot agentic layer —
  `list_invoices`, `get_invoice` (READ ONLY, `include_payments=False`).
  Invoice axis only per the off-books boundary; no issuing/voiding tools.

- refactor(invoices): dedup the ``toListItem`` builder (3 sites → 1 helper) in ``useInvoices``.
- refactor(invoices): drop the hardcoded Spanish ``PAYMENT_METHOD_LABELS`` map and route ``getPaymentMethodLabel`` through the new shared ``paymentMethodLabel`` util (reads the canonical ``invoice.payments.methods.*`` i18n keys; adds the missing ``insurance`` translation).
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast pattern (14 sites) in ``useInvoices`` now that ``useApi`` accepts ``object`` payloads.
- refactor(perms): migrate hardcoded ``can('billing.{read,write,admin}')`` strings on the invoice list and detail pages to ``PERMISSIONS.billing.*``.
- refactor(errors): switch ``catch (e: any)`` to ``catch (e: unknown)`` on the invoice detail page and route through the shared ``errorMessage`` helper.
- perf(invoices-list): drop the ``select_from(query.subquery())``
  count anti-pattern. ``COUNT(Invoice.id)`` runs directly over the
  filter set, and the search-by-patient-name join is added only to
  the count when ``search`` is active (no overhead otherwise).
- perf(pdf): ``InvoicePDFService.generate_pdf`` is now ``async`` and
  offloads the WeasyPrint render to ``asyncio.to_thread`` so a slow
  PDF (compliance QR, long invoices) no longer stalls the event
  loop. All call sites updated.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).

### Added (lists redesign, 2026-05-14)

- `GET /api/v1/billing/invoices` accepts `sort=field:dir` (whitelist:
  `issue_date`, `due_date`, `total`, `created_at`, `invoice_number`).
- `/invoices` list page rewritten on `DataListLayout` + `FilterBar` +
  `useListQuery`. Card view <md, URL-synced filters, sort dropdown,
  date range filter in the main toolbar. Existing compliance slots
  (`invoice.list.toolbar.filters`, `invoice.list.row.meta`)
  preserved.

- **Payment domain extracted to its own `payments` module (issue #53, ADR 0010).**
  - Billing no longer owns the `Payment` model, `PaymentService`, or
    `InvoiceWorkflowService.record_payment` / `void_payment`. Those move
    to `app.modules.payments`.
  - New `InvoicePayment` model + `bil_0004_invoice_payments` migration —
    one row per imputation of a Payment to an Invoice. Multiple rows
    per invoice (parcial cobros) and per payment (allocations across
    invoices) are supported.
  - `Invoice.total_paid` / `Invoice.balance_due` columns dropped. The
    values are computed by `BillingService.compute_paid_summary` from
    `invoice_payments` minus proportional refunds.
  - New endpoint `POST /api/v1/billing/invoices/{id}/payments` is the
    "factura + cobro" orchestrator: it creates a Payment via the
    payments module, links it via `InvoicePayment`, and recomputes the
    invoice status. For anticipos against budgets, use the payments
    module directly.
  - New event subscription `payment.refunded` recomputes the invoice
    status of any invoice with an `InvoicePayment` pointing to the
    refunded payment.
  - `BillingComplianceHook.on_payment_recorded` was previously defined
    but never invoked. The new orchestrator now calls it after creating
    the link (placeholder until verifactu wires it up).
  - Manifest: `depends` now lists `"payments"`.

- `PatientBillingSummary` (patient detail → Administración → Facturación)
  now paginates invoices at page_size=20 with the shared `PaginationBar`,
  replacing the previous hard-coded `page_size: 100` single-page dump.
- **Generic compliance summary in invoice list** — `InvoiceListResponse`
  now exposes `compliance_data` (the same JSONB the model already
  carries). Compliance modules (Verifactu et al.) read it via slots
  to render their own badge in each row without billing knowing the
  shape per country.
- **Generic `compliance_severity` query filter** on
  `GET /api/v1/billing/invoices`. Whitelisted values
  (`ok|warning|pending|error`). Filter is country-agnostic — applies
  via JSONB path over any country key whose `severity` matches. The
  vocabulary is shared across compliance modules; billing never
  imports them.
- **Three new module slots** in the invoice screens for compliance
  modules to plug into:
  - `invoice.list.row.meta` — extra chip next to the status badge in
    each list row. Ctx: `{invoice, clinic}`.
  - `invoice.list.toolbar.filters` — extra filter widgets in the list
    toolbar. Ctx: `{severity, onChange, clinic}`.
  - `invoice.detail.header.meta` — extra badge next to the invoice
    number/status in the detail header. Ctx: `{invoice, clinic}`.
- **`PATCH /api/v1/billing/invoices/{id}/billing-party`** — edit
  `billing_name` / `billing_tax_id` / `billing_address` on an issued
  invoice when the country compliance hook signals the latest fiscal
  record is correctable (e.g. Verifactu `rejected`). Triggers the
  hook's `regenerate_after_party_change` so the user does not have to
  chase the compliance queue. Optimistic locking via
  `expected_updated_at`.
- **`Invoice.pdf_stale`** boolean (migration `bil_0002`). Compliance
  hooks set it to `True` after regenerating their fiscal record so
  the previously-rendered PDF (with stale QR / huella) is flagged in
  the UI for re-download.
- **`BillingComplianceHook` interface extended** with
  `can_edit_billing_party()` (gates the new PATCH endpoint) and
  `regenerate_after_party_change()` (re-renders the compliance
  record after a party edit). Default impls are no-ops so existing
  hooks keep working.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- `InvoicePDFService.generate_pdf()` accepts an optional
  `extra_pdf_data` dict produced by a registered
  `BillingComplianceHook.enhance_pdf_data()`. The PDF endpoints
  (`GET /invoices/{id}/pdf` and its preview sibling) now resolve the
  hook from `BillingHookRegistry` and forward its dict so country
  modules can inject a QR (`compliance_qr_png_b64`) and legal
  notices. Billing remains country-agnostic — it only reads the
  generic dict it receives.
- Invoice detail page exposes a generic `<ModuleSlot
  name="invoice.detail.compliance">` so country compliance modules
  (Verifactu-ES today, factur-x-FR or sdi-IT later) can render a
  status panel next to the totals without billing importing them.

## 0.1.0 — initial

- Invoice + credit note workflow with PDF generation.
- Payment recording (full and partial).
- `BillingComplianceHook` extension point for compliance modules.
- Events: `invoice.issued`, `invoice.sent`, `invoice.paid`.
