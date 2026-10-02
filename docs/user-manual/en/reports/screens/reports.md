---
module: reports
screen: dashboard
route: /reports
related_endpoints:
  - GET /api/v1/reports/scheduling/first-visits
  - GET /api/v1/reports/scheduling/funnel
related_permissions:
  - reports.billing.read
  - reports.budgets.read
  - reports.scheduling.read
related_paths:
  - backend/app/modules/reports/frontend/pages/reports/index.vue
  - backend/app/modules/reports/frontend/composables/useDashboardSnapshot.ts
  - backend/app/modules/reports/frontend/components/dashboard/
last_verified_commit: 2195ad0e
---

# Clinic dashboard

Entry page for the reports area. Executive view with the key
indicators a clinic owner or manager needs, all filterable by date
range — except the metrics marked as *point-in-time*.

## At a glance

- **Hero row (4 tiles).** Cash collected, patient credit balance,
  total production, and a payment-method breakdown.
- **Charts row.** Collections over time (with refunds overlaid) and
  production by doctor.
- **Operations row.** New patients, no-show rate, and average
  collected ticket.
- **Attention.** Aging receivables grouped by age (0-30 / 31-60 /
  61-90 / 90+).
- **Drilldown.** Cards linking to the detailed billing, budgets and
  agenda pages — the previous navigation flow is preserved.

## Date-range filter

- Single `Period` filter pinned to the top of the page.
- Default range is the current month.
- Presets: today, last 7, last 30, this month, this quarter, this
  year.
- The range is persisted in the URL (`?from=…&to=…`) so a manager
  can bookmark a period.

## Point-in-time metrics

Two tiles do not change with the filter: they show the current
state of the clinic.

- **Patient credit balance** — money paid in advance by patients
  not yet allocated to budgets or invoices.
- **Aging receivables** — outstanding debt grouped by age.

Both display a `Today` badge to avoid misreading them as
date-filtered.

## Permissions

| What you see | Required permission |
|--------------|--------------------|
| Cash collected, patient credit, production, methods, charts, avg ticket, aging | `payments.reports.read` (detail: the payments reports screen) |
| New patients, no-show rate | `reports.scheduling.read` |
| Billing drilldown | `reports.billing.read` |
| Budgets drilldown | `reports.budgets.read` |
| Agenda drilldown | `reports.scheduling.read` |

If a role lacks a permission, that tile is hidden and the grid
reflows without gaps.

## Troubleshooting

- **No metrics show up.** Your role lacks the required
  permissions. Ask an admin from *Settings → Users → Roles*.
- **Payments tiles empty.** No payments recorded in the range.
  Verify the payments module is in use or widen the period.
- **Production at zero.** Production tracks completed treatments
  (session completions or odontogram entries). If the team doesn't
  mark treatments as done, they won't appear.
- **Numbers don't match the detail pages.** Detail pages work on
  invoices; the dashboard works on payments. They are deliberately
  separate axes — clinics may keep some work off-invoice, so
  comparing collected vs invoiced isn't a meaningful signal.
