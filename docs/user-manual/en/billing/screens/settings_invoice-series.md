---
module: billing
screen: invoice-series
route: /settings/invoice-series
related_endpoints:
  - GET /api/v1/billing/series
  - POST /api/v1/billing/series
  - POST /api/v1/billing/series/{series_id}/reset
  - PUT /api/v1/billing/series/{series_id}
related_permissions:
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/pages/settings/invoice-series/index.vue
  - backend/app/modules/billing/router.py
last_verified_commit: b1b82f5
---

# Invoice series

Configuration of the numeric series that assign a fiscal number to
invoices when issued. Manage prefixes, counters, and which one is
active per fiscal year.

## At a glance

- **Series structure.** Code (`FAC`, `ABO`, …), readable prefix
  (`FACT-2026-`), current counter, fiscal year, document type
  (`invoice` or `credit_note`), and active flag.
- **Active per type and year.** Only one series per type / year can
  be active. Issuing an invoice uses the active series for its
  type and consumes its counter.
- **Counter reset.** Only when the series has not yet been used
  this fiscal year. Once the first invoice is issued, reset is
  blocked to preserve fiscal audit.
- **Yearly reset switch.** Turning *Reset numbering every year* on in the middle
  of a year does not restart the numbering: this year's invoices
  keep counting from the last number, and the series starts again
  at 1 next January.
- **Permissions.** All series management requires `billing.admin`.
  Other roles can browse the list but not edit.

## Create a series

> Requires `billing.admin`.

1. Click **New series**.
2. Define code, prefix, fiscal year, and type (invoice or credit
   note).
3. Mark *Active* if it should replace the current one; on save,
   the previous one is deactivated automatically for the same
   (type, year).

## Reset counter

> Requires `billing.admin`. Only on unused series for the fiscal
> year.

1. Pick the series and click **Reset**.
2. The counter goes back to 0. Blocked if any invoice is already
   issued against this series this fiscal year.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View the series list | `billing.read` |
| Create, edit, activate/deactivate, reset | `billing.admin` |

## Troubleshooting

- **"Cannot reset counter".** Invoices have already been issued
  against this series this fiscal year; blocked for safety. Create
  a new series for next year.
- **A new invoice does not assign a number.** No active series for
  the type (invoice or credit note) and current year. Activate or
  create one.
- **No edit options.** Your role is not `billing.admin`.
