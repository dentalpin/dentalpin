---
module: payroll
screen: reports
route: /payroll/reports
last_verified_commit: 0b59a2a2
related_endpoints:
  - GET /api/v1/payroll/reports/monthly?month=
  - GET /api/v1/payroll/reports/annual?year=
related_permissions:
  - payroll.reports.read
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/reports/index.vue
---

# Reports

Found under the **Reports** payroll sidebar entry (admin only). Two
cards side by side: a monthly rollup for a typed `YYYY-MM` month and
an annual rollup for a year, both in the clinic currency.

## What you can do

- **Monthly**: type the month and load entry count, total gross,
  total deductions and total net.
- **Annual**: type the year (defaults to the current one) and load
  period count plus the same totals across the year.
