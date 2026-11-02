---
module: billing
screen: detail
route: /invoices/[id]
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
  - POST /api/v1/billing/invoices/{invoice_id}/credit-note
  - POST /api/v1/billing/invoices/{invoice_id}/issue
  - POST /api/v1/billing/invoices/{invoice_id}/items
  - POST /api/v1/billing/invoices/{invoice_id}/payments
  - POST /api/v1/billing/invoices/{invoice_id}/send-email
  - POST /api/v1/billing/invoices/{invoice_id}/void
  - PUT /api/v1/billing/invoices/{invoice_id}
  - PUT /api/v1/billing/invoices/{invoice_id}/items/{item_id}
related_permissions:
  - billing.read
  - billing.write
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/[id]/index.vue
  - backend/app/modules/billing/router.py
last_verified_commit: edc08ff
---

# Invoice detail

View of one invoice. Header with legal data (issuer, receiver, tax
ID, address), line items, totals, and a sidebar with linked
payments, history, and fiscal submission state (verifactu). From
here you issue, send to the patient, and — when appropriate — void
or issue a credit note.

## At a glance

- **Linked quote and plan.** An invoice created from a quote links back to it and, when that quote came from a treatment plan, to the plan as well.
- **Legal data** — receiver (patient or third-party payer), tax ID,
  fiscal address, series + number (on `issued`). If the payer is
  not the patient, a *Different payer* chip is shown.
- **Linked payments.** A list of `invoice_payments` with amount and
  method, plus the **Collect** button (`issued`/`partial` invoices).
  The payment is recorded in the `payments` module and linked here in
  the same operation. If the invoice was created from a quote, the
  payment is allocated to that quote: the quote's *Paid* card and the
  patient record reflect it immediately. The reverse holds too:
  collecting on the quote applies to its issued invoices, and issuing
  an invoice from a quote that was already collected (deposit) makes
  the invoice born `paid`.
- **PDF.** Two formats: draft (watermarked preview) and final (only
  for `issued`). PDF generation uses WeasyPrint. When a line uses a
  VAT type carrying a statutory note (e.g. the Spanish exemption,
  art. 20.Uno.5º LIVA, seeded by the `es` preset), the note prints in
  the legal-notices block. The footer shows the generation date and
  time in the clinic's timezone.
- **History.** Status changes and key events in chronological order.
- **VeriFactu.** When the module is installed, issuing the invoice
  queues the AEAT submission. State (`pending`, `sent`, `rejected`)
  is shown in the sidebar.

## Issue an invoice

> Requires `billing.write`.

1. Verify that the legal data and line items are correct. Once
   issued, the document cannot be edited. If the patient has no tax
   id (nor DNI/NIE), the draft shows *Missing data* and the primary
   button becomes **Complete data**: it opens the patient's billing
   modal and returns to the invoice on save.
2. Click **Issue**. The active series assigns the fiscal number,
   `invoice.issued` is published, and the document is frozen.
3. If `verifactu` is installed, the hook will queue the AEAT
   submission and you'll see the state on the sidebar.

## Send by email

> Requires `billing.write`.

1. Click **Send by email**. The PDF is sent to the receiver's
   contact email.
2. `invoice.sent` is published. The history records the send.

## Void or issue a credit note

> Voiding requires `billing.admin`; issuing a credit note requires
> `billing.write`.

- **Void** — marks the invoice as `void`. Its number stays in the
  history for audit. Admin only.
- **Create credit note** — issues a credit note tied to the source
  invoice's amounts. Goes through the same issuing workflow. All the
  credit notes of one invoice together, drafts included, cannot exceed
  its total; once it is fully credited, a new one is refused with the
  amount still creditable. Delete a draft credit note to free its amount.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View invoice, PDF, history | `billing.read` |
| Edit draft, issue, send email, create credit notes | `billing.write` |
| Void an issued invoice | `billing.admin` |

## Troubleshooting

- **Cannot edit lines.** The invoice is no longer in `draft`. Void
  and issue a new one, or issue a partial credit note.
- **The downloaded PDF is the watermarked preview.** The invoice
  is in `draft` or `void`. The final PDF only exists for issued
  invoices.
- **VeriFactu is `rejected`.** Check the sidebar or the
  `verifactu` module for the reason. Usually requires editing
  issuer or receiver data and re-submitting manually.
- **I collected from the patient record and the invoice is still
  unpaid.** The payment was left *on account* (no quote). Under
  Administration → Payments use **Assign to quote…** on that payment;
  if the invoice comes from that quote it is applied automatically.
