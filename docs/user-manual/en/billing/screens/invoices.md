---
module: billing
screen: list
route: /invoices
related_endpoints:
  - DELETE /api/v1/billing/invoices/{invoice_id}
  - DELETE /api/v1/billing/invoices/{invoice_id}/items/{item_id}
  - GET /api/v1/billing/invoices
  - GET /api/v1/billing/invoices/{invoice_id}
  - GET /api/v1/billing/invoices/{invoice_id}/history
  - GET /api/v1/billing/invoices/{invoice_id}/payments
  - GET /api/v1/billing/invoices/{invoice_id}/pdf
  - GET /api/v1/billing/invoices/{invoice_id}/pdf/preview
  - GET /api/v1/billing/patients/{patient_id}/summary
  - GET /api/v1/billing/series
  - GET /api/v1/billing/settings
  - PATCH /api/v1/billing/invoices/{invoice_id}/billing-party
  - POST /api/v1/billing/invoices
  - POST /api/v1/billing/invoices/from-budget/{budget_id}
  - POST /api/v1/billing/invoices/{invoice_id}/credit-note
  - POST /api/v1/billing/invoices/{invoice_id}/issue
  - POST /api/v1/billing/invoices/{invoice_id}/items
  - POST /api/v1/billing/invoices/{invoice_id}/payments
  - POST /api/v1/billing/invoices/{invoice_id}/send-email
  - POST /api/v1/billing/invoices/{invoice_id}/void
  - POST /api/v1/billing/series
  - POST /api/v1/billing/series/{series_id}/reset
  - PUT /api/v1/billing/invoices/{invoice_id}
  - PUT /api/v1/billing/invoices/{invoice_id}/items/{item_id}
  - PUT /api/v1/billing/series/{series_id}
  - PUT /api/v1/billing/settings
related_permissions:
  - billing.read
  - billing.write
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/index.vue
  - backend/app/modules/billing/router.py
last_verified_commit: 0000000
---

# Invoice list

The operational invoice queue: drafts in progress, issued invoices,
credit notes, voided documents. From here you search, filter, and
open invoices to issue, email, or void them.

## At a glance

- **States.** `draft` (editable draft), `issued` (a fiscal number
  is assigned — no longer editable), `paid` (fully collected),
  `void` (voided). Credit notes are a separate document type
  (`credit_note`) that shows up alongside their related invoices.
- **Fiscal numbering.** Only **issuing** an invoice assigns the
  series number. Deleting a draft does not consume a number;
  voiding an issued invoice leaves it in the audit history.
- **Search and filters.** Search by number, patient, or tax ID.
  Filters: status, issue date range, series, and *with budget*.
- **Compliance.** When the `verifactu` module is installed,
  issuing an invoice queues the AEAT submission through the
  `invoice.issued` hook. The submission state is visible on the
  detail.

The **Historical** badge identifies imported invoices. Their totals remain available in the list and in billing reports on the original issue date. Historical invoices do not appear in overdue results.

## Find an invoice

1. Type the number (`FACT-2026-####`), patient name, or tax ID
   into the search box.
2. Apply filters: status, series, dates.
3. Click a row to open the [detail](./invoices_id.md).

## Create an invoice

> Requires `billing.write`.

- **From budget** — on an accepted budget detail, *Create invoice*.
  Copies the items into the draft.
  [See invoice from budget](./invoices_from-budget_budgetId.md).
- **Free invoice** — from the list, **New invoice**.
  [See new invoice](./invoices_new.md).

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| List, search, and download PDFs | `billing.read` |
| Create drafts, edit, issue, send email, create credit notes | `billing.write` |
| Void an issued invoice | `billing.admin` |

## Troubleshooting

- **A newly created invoice is missing.** An active filter is
  excluding it. Clear filters or search by number.
- **Editing is blocked.** The invoice is already `issued`. To
  amend legal data, issue a credit note (*Create credit note*) and
  invoice again.
- **"No active series".** No invoice series is marked active for
  this fiscal year under *Settings → Invoice series*. Activate or
  create one.
