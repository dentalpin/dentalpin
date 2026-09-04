---
module: payroll
---

# Payroll

Staff payroll for clinic admins. Profiles hold salary terms with
encrypted bank/tax data; monthly periods collect raw entries; reports
roll them up. No tax computation in v1.

## Workflows

- **Profiles**: create one profile per staff user (base amount,
  currency, bank account, tax ID). Secrets are masked everywhere —
  only the last 4 digits ever show. Re-enter a full value to change
  it; omitting it keeps the stored one. Deactivate instead of
  deleting.
- **Periods**: open one `YYYY-MM` period at a time; move it
  draft → closed → paid. Closed periods lock their entries.
- **Entries**: record gross, deductions and net per employee (net must
  equal gross minus deductions). One entry per employee per period.
- **Reports**: monthly rollup per period, annual rollup per year, in
  the clinic currency.
