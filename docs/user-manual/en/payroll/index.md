---
module: payroll
---

# Payroll

Staff payroll for clinic admins (admin role only). Four pages under
the payroll sidebar entries:

- **[Profiles](./screens/profiles.md)** — one profile per staff user
  (base amount, currency, bank account, tax ID). Secrets are masked
  everywhere — only the last 4 digits ever show. Re-enter a full value
  to change it; omitting it keeps the stored one. Deactivate instead
  of deleting.
- **[Periods](./screens/periods.md)** — open one `YYYY-MM` period at a
  time; move it draft → closed → paid with confirmation. Closed
  periods lock their entries.
- **[Period detail](./screens/period-detail.md)** — per-employee
  entries (gross, deductions, net as entered; net must equal gross
  minus deductions, enforced in the form and the API).
- **[Reports](./screens/reports.md)** — monthly rollup per period,
  annual rollup per year, in the clinic currency. No tax computation
  in v1.
