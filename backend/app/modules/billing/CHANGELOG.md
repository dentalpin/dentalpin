# Changelog — billing module

## Unreleased

- fix(#127): every icon-only button in the module's frontend has an i18n-sourced `aria-label` (screen readers announced them as just "button").

- i18n(#131/#275): invoice-line descriptions from catalog names now fall
  back to any non-empty translation after `es→en→fr→pt→ta`, so items
  created under a core-only locale (de, hu, and future ones) never
  degrade to "Unknown treatment".
- fix(#204): invoice PDF polish — the footer prints the real generation datetime in the clinic's timezone (`date.today()` through `%H:%M` always read "00:00"); the per-line VAT rate uses the same locale-aware formatting as the amounts (`0%`/`8,5%`, never `0.0%`); and the PDF endpoints prepend the lines' `VatType.legal_note` statutory clauses (e.g. the Spanish dental exemption, art. 20.Uno.5º LIVA) to the legal-notices block via `vat_legal_notes_for_invoice`.
- fix(#203): the back link on invoice detail/new rendered the raw key `actions.back` when arriving from the patient page — the key never existed in any locale; use `common.back` ("Volver").

- fix(#181): from-budget wizard — the per-row discount caption follows the quantity being invoiced and unselected rows show the quote's net price (after global discount). Invoice detail exposes `treatment_plan` (read-time lookup through the budget module, no FK) and links to the plan. Patient billing summary exposes `total_discount`.
- fix(#175): voiding or deleting a draft invoice, editing/removing one of its lines, or issuing a credit note now releases the quote lines it consumed. `BudgetItem.invoiced_quantity` is recomputed from the live invoice lines (`resync_invoiced_quantities`) instead of incremented on create; `create_from_budget` takes the budget row lock so two wizards can't over-invoice the same line.
- fix(#206): issue snapshot reads `Patient.effective_billing_*` (no duplicated name fallback). "Faltan datos" now shows on the from-budget wizard and turns the draft's *Emitir* action into *Completar datos*; every "edit patient billing" link opens the billing modal and returns to the invoice. Payment terms are hidden (form) and omitted (PDF, #204 §4) when the budget is fully collected / the invoice has no balance due.
- docs(#91): `BillingHookRegistry` docstring shows the real hook (`BaseModule.on_activate`) instead of the never-implemented `on_load/on_unload`.
- refactor(#184): the invoice edit page no longer casts the embedded patient brief to `Patient`; a `displayedPatient` computed falls back from the user's pick to the invoice brief, and `patient_id` is only sent when a different patient was actually chosen.
- fix(#184): type-check clean. `GET /invoices/{id}/payments` returns `InvoicePaymentDetailResponse` (link row + embedded `PaymentResponse`) — the patient billing summary rendered `payment_date`/`method` the link row never had; `InvoiceDetail.invoice_payments` mirrors the API (`payments` did not exist); invoices embed billing's own patient brief (`InvoicePatientBrief`, with billing fields); the from-budget page loads the full patient for the billing card (the budget brief has no billing fields, so it always showed the fallback); the new-invoice form drops the dead billing inputs the API ignores; readonly items typed `DeepReadonly` where only read.
- docs(#183): `on_clinic_created` documented as own-session — published after setup commits, and seeding series must not stretch the signup transaction.
- fix(#178): budget ↔ invoice bridge (`payment_bridge.py`). Payments
  allocated to a budget are imputed to that budget's open invoices
  (FIFO, preferring the invoice being collected on) and unlinked on
  reallocation, via a transactional `payment.allocated` subscriber;
  `issue_invoice` sweeps anticipos already collected on the quote into
  the new invoice; the orchestrator `POST /invoices/{id}/payments`
  allocates to `invoice.budget_id` when set (quote card now shows
  invoice collections). `payment.refunded` handler is transactional —
  invoice status actually moves on refund (it silently didn't before).
  Patient billing summary `total_paid` is refund-aware. Lock order:
  budget row → invoice rows.

- feat(onboarding): getting-started rule `invoice-series` (frontend plugin) — flags a clinic without invoice series.

- feat(onboarding): subscribe to `clinic.created` — auto-create default `FAC`/`RECT` series so the first invoice can be issued without visiting settings.

- fix(from-budget): invoices created from a quote now carry the quote's
  global discount (prorated per line, ex-tax) on top of the line
  discount; absolute line discounts are prorated by invoiced quantity
  (no more double-charging on partial invoicing); absolute discounts are
  clamped to the line subtotal. The wizard preview uses the budget API's
  `global_discount_share` so it matches the persisted invoice (issue #167).

- i18n: add `ta` fallback to invoice description resolution in
  service layer so Tamil-localized treatment names appear on invoices.

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(ui): surface the API error instead of a generic toast in the invoice pages (issue, void, credit note, send, delete, edit, create) and both PDF downloads.
  `catch {}` discarded the server's message, so any failure read as
  "Error" with no way to tell what went wrong. Now via
  `errorMessage()` / `errorDetail()`.

- i18n: add `pt` fallback to invoice description resolution in
  service layer so Portuguese-localized treatment names appear on invoices.

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
