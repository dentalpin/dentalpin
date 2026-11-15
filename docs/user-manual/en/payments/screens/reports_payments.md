---
module: payments
screen: payments
route: /reports/payments
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
  - backend/app/modules/payments/frontend/pages/reports/payments/index.vue
last_verified_commit: 71402014
---

# /reports/payments

Payment analytics dashboard. The page wraps the six `/api/v1/payments/reports/*`
endpoints into a single calm-design view and lets you drill straight
into the underlying `/payments` (or `/patients`) list at every step.

## Permissions

Gated by `payments.reports.read`. Roles that include it by default:
admin, dentist, receptionist. Other report rows do not appear until
the user also has `payments.record.read` (needed for the drill-down
target).

## Layout

The dashboard reads top-down:

1. **Hero row** — two oversized cards.
   - *Net collected* shows the period total, a percentage delta versus
     the previous equal-length period, and a sparkline of the net
     across the trend buckets.
   - *Outstanding receivable* shows the clinic's pending balance plus
     four mini bars (0–30, 31–60, 61–90, 90+ days) with per-bucket
     totals and patient counts. Click a bar to jump to `/patients`
     filtered by debt.
2. **Secondary KPIs** — collected, refunded, patient credit, refund
   ratio. The first two are clickable; collected jumps to the period
   in `/payments`, refunded adds `has_refunds=true`.
3. **Collection trend** — area chart of net per bucket with a dashed
   refund overlay. Granularity toggle (day / week / month) on the
   header. Click any point to drill down to that bucket.
4. **By method** — donut + legend. Click a slice → `/payments?method=…`.
5. **By professional** — top 8 bars of treatment performed (earned),
   not collected. Click jumps to `/payments` in the period.
6. **Receivables aging** — full-width bars for each bucket. Each row
   drills to `/patients?has_debt=true`.
7. **Refunds by reason** — distribution of refunds by recorded reason.

## Filters

- Period: `FilterDateRange` with quick presets (Today / 7d / 30d /
  This month / Quarter / Year). Default is the last 90 days.
- Granularity: only affects the trend chart.
- On narrow screens, receivables-aging buckets use two columns; wider screens
  show four.

## Empty states

If the selected period has zero data the secondary sections collapse
into a single empty card. Each section renders its own empty state
when only that section has no data (no methods, no professionals,
no refunds, no receivable).

## Off-books safety

This dashboard never compares paid against invoiced or earned against
invoiced. The professional breakdown is treatment performed, not
billed. See `payments/CLAUDE.md` "Gotchas" and ADR 0010.

## Related screens

- `/payments` — list of every payment, target of most drill-downs.
- `/patients` with `has_debt=true` — target of aging drill-downs.

