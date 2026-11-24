---
module: payments
screen: list
route: /payments
related_endpoints:
  - GET /api/v1/payments
  - GET /api/v1/payments/budgets/{budget_id}/allocations
  - GET /api/v1/payments/filters/budgets-by-status
  - GET /api/v1/payments/filters/patients-with-debt
  - GET /api/v1/payments/patients/{patient_id}/ledger
  - GET /api/v1/payments/reports/aging-receivables
  - GET /api/v1/payments/reports/by-method
  - GET /api/v1/payments/reports/by-professional
  - GET /api/v1/payments/reports/refunds
  - GET /api/v1/payments/reports/summary
  - GET /api/v1/payments/reports/trends
  - GET /api/v1/payments/{payment_id}
  - GET /api/v1/payments/{payment_id}/refunds
  - POST /api/v1/payments
  - POST /api/v1/payments/summary/by-budgets
  - POST /api/v1/payments/summary/by-patients
  - POST /api/v1/payments/{payment_id}/reallocate
  - POST /api/v1/payments/{payment_id}/refunds
related_permissions:
  - payments.record.read
  - payments.record.write
  - payments.record.refund
  - payments.reports.read
related_paths:
  - backend/app/modules/payments/frontend/pages/payments/index.vue
  - backend/app/modules/payments/router.py
last_verified_commit: 0a9b730
---

# Payment list

The clinic's operational cash log. Each row is a payment received
from a patient, with its gross amount, the allocations to budgets or
*on-account*, and the refunded total if any. Record a new payment,
reallocate it, or issue a refund from the same screen.

## At a glance

- **Patient-centric, not invoice-centric.** Every payment belongs to
  a patient and splits into *allocations* (budget or `on_account`).
  Invoicing lives in the `billing` module and links back to these
  payments — never the reverse.
- **Filters live in the URL** — method, patient, date range, *With
  refunds*, *With on-account balance*. Sharing the link shares the
  filters.
- **Search** matches the patient's name or the payment reference
  across every payment, not just the visible page. Picking several
  methods shows payments in any of them; the counter and pager
  reflect the filtered total.
- **Sort:** payment date descending by default. Amount sort is also
  available.
- **Off-books.** The list never crosses *paid* against *invoiced* —
  this is a deliberate product decision (see ADR 0010).
- **Refund state:** if a payment has refunds, the refunded amount
  shows in red under the gross amount. The ↺ button only appears
  when net balance remains and your role can refund.

## Record a payment

> Requires `payments.record.write`.

1. Click **New payment** in the header (or from the budget sidebar
   card on the patient record).
2. Pick the patient. Choose the method and the payment date. The
   methods sit in two groups: **Record a payment already received**
   (cash, card, bank transfer, direct debit, insurance, or *other*)
   writes the money down as it came in, while **Collect now** starts a
   collection through an installed gateway. The second group is only
   there when a gateway module offers a rail for this clinic.
3. Pick the **Apply to** target: one of the patient's open quotes
   (listed by number and amount) or *Patient credit (on account)*.
   On-account money stays as the patient's credit and **is not applied
   to any invoice or quote** until you assign it — the form says so
   under the selector. To split across several targets open
   *Advanced options*; the sum of allocations must equal the gross
   amount.
4. **Save**. `payment.recorded` and one `payment.allocated` per
   allocation are published. The quote's *Paid / Outstanding* sidebar
   card refreshes immediately and, if the quote has issued invoices,
   the payment is applied to them (FIFO) in the same operation: the
   invoice moves to `partial`/`paid` with no extra step.

## Reallocate a payment

> Requires `payments.record.write`.

1. Open the payment by clicking on its row, or from the patient
   record.
2. Use **Reallocate** to move amounts between budgets or between a
   budget and *on-account*. Each change publishes
   `payment.allocated`; invoices of the source quote are unlinked and
   those of the target quote are applied, all in one transaction.
   From the patient record (Administration → Payments) the row menu
   offers **Assign to quote…** for the common case: a deposit left on
   account that should now be applied.

## Refund

> Requires `payments.record.refund`. Default is admin and dentist
> only. Admins may grant this to the front desk under *Settings →
> Users → Roles*.

1. Click ↺ on the payment row (only visible while net balance
   remains).
2. Enter the amount (partial or full) and the reason. The refund
   never deletes the original payment: it lands as a `Refund` row
   and is subtracted from the *net* total.
3. **Confirm**. `payment.refunded` is published and the row shows
   `− 50.00 €` under the gross amount.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View list, allocations, patient ledger | `payments.record.read` |
| Record a payment and reallocate it | `payments.record.write` |
| Issue a refund | `payments.record.refund` |
| Access the payment reports | `payments.reports.read` |

## Troubleshooting

- **The list is empty with active filters.** Click **Clear filters**
  in the toolbar (the chip with the counter). If nothing still
  shows, check the date range — none is set by default.
- **Save rejects with "allocation sum mismatch".** The total of the
  allocations must match the gross amount. Adjust a value or add an
  *on-account* allocation for the remainder.
- **No ↺ button even though my role should refund.** The payment is
  already 100% refunded (net is zero). Refunds only run while net
  balance remains.
- **An invoice is not reflected as paid on its budget.** The invoice
  links to the payment from the `billing` module. Make sure the
  payment is allocated to the right budget.
