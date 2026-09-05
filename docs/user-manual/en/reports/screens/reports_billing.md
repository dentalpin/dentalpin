---
module: reports
screen: billing
route: /reports/billing
related_endpoints:
  - GET /api/v1/reports/billing/aging
  - GET /api/v1/reports/billing/by-payment-method
  - GET /api/v1/reports/billing/by-professional
  - GET /api/v1/reports/billing/gaps
  - GET /api/v1/reports/billing/issued-trend
  - GET /api/v1/reports/billing/overdue
  - GET /api/v1/reports/billing/summary
  - GET /api/v1/reports/billing/vat-summary
related_permissions:
  - reports.billing.read
  - reports.financial.read
related_paths:
  - backend/app/modules/reports/frontend/pages/reports/billing.vue
  - backend/app/modules/reports/router.py
last_verified_commit: b1b82f5
---

# Billing reports

Billing dashboard. Summarizes what has been invoiced and what is
pending, with breakdowns by professional, payment method, VAT,
overdue invoices, and series gaps. Useful for month-end close,
reconciliation, and VAT filing.

## At a glance

- **Default range** — last 90 days. The date filter lives in the
  header and applies to every section except the *as-of-now* ones
  (overdue, gaps).
- **Summary** — total invoiced, invoice count, and average per
  invoice for the range.
- **By payment method** — breakdown of what has been invoiced by
  method. **Note:** the *collected* breakdown lives in
  [payment reports](../../payments/screens/reports_payments.md);
  here you see *what has been invoiced*.
- **By professional** — invoicing attributed to each professional.
- **VAT** — aggregate by VAT type. Handy for preparing the period's
  fiscal return.
- **Overdue and gaps** — past-due invoices and numbering gaps in
  series, if any.
- **Aging** — outstanding invoice totals per age bucket
  (0–30/31–60/61–90/90+ days past due, issued amounts only). Same
  numbers as the dashboard aging card; append `?format=csv` to the
  endpoint for the spreadsheet.
- **Issued trend** — issued totals per month over the range
  (`?format=csv` available).

## Drill-downs

- Any section representing individual invoices (overdue, gaps) has
  *Open in /invoices* that takes you to the filtered list.
- To audit a specific professional or payment method, use the
  invoice list filters with the same range.

## Off-books safeguard

This report **does not** cross *collected* against *invoiced*: the
comparison is intentionally avoided (ADR 0010). If you need to
know what is left to collect, go to
[/reports/payments](../../payments/screens/reports_payments.md),
which does not compare against `invoiced`.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View any of the sections | `reports.billing.read` |
| Open the underlying invoice list (drill-down) | `billing.read` |

## Troubleshooting

- **A section is empty.** The default range captures no data, or
  the filter removes everything. Widen the range.
- **Series gaps look odd.** If you only emit drafts you don't
  consume a number; a real gap only appears when an issued invoice
  is deleted (not allowed) or with old series resets. Investigate
  in the list.
- **VAT doesn't match your filing.** Make sure invoices in the
  range are issued (not drafts) and the catalog VAT types are
  correctly set under *Settings → VAT types*.
