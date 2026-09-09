---
module: reports
last_verified_commit: 0000000
---

# Reports — technical overview

Read-only analytics over billing, budgets, scheduling, and (roadmap
#230) financial, patient-stats, and operational families. Every
endpoint is a `GET` gated by its family's `reports.<family>.read`
permission; list endpoints accept `?format=csv` for export. No events
published or consumed; no mutations.

## Families

- **billing / budgets / scheduling** — the original families
  (per-endpoint list under API surface below).
- **financial** (roadmap #230) — invoice-axis only (never payments):
  `GET /billing/aging` (outstanding buckets) +
  `GET /billing/issued-trend` (issued totals over time), both under
  `reports.financial.read`, plus the `financial_report` copilot tool.
  An off-books guard test pins the invoice-axis scope.

## API surface

- `GET /api/v1/reports/billing/by-payment-method`
- `GET /api/v1/reports/billing/by-professional`
- `GET /api/v1/reports/billing/gaps`
- `GET /api/v1/reports/billing/overdue`
- `GET /api/v1/reports/billing/summary`
- `GET /api/v1/reports/billing/vat-summary`
- `GET /api/v1/reports/budgets/by-professional`
- `GET /api/v1/reports/budgets/by-status`
- `GET /api/v1/reports/budgets/by-treatment`
- `GET /api/v1/reports/budgets/summary`
- `GET /api/v1/reports/scheduling/by-cabinet`
- `GET /api/v1/reports/scheduling/by-day-of-week`
- `GET /api/v1/reports/scheduling/by-professional`
- `GET /api/v1/reports/scheduling/duration-variance`
- `GET /api/v1/reports/scheduling/first-visits`
- `GET /api/v1/reports/scheduling/funnel`
- `GET /api/v1/reports/scheduling/punctuality`
- `GET /api/v1/reports/scheduling/summary`
- `GET /api/v1/reports/scheduling/waiting-times`

## Frontend

- `backend/app/modules/reports/frontend/pages/reports/index.vue` → `/reports`
- `backend/app/modules/reports/frontend/pages/reports/billing.vue` → `/reports/billing`
- `backend/app/modules/reports/frontend/pages/reports/budgets.vue` → `/reports/budgets`
- `backend/app/modules/reports/frontend/pages/reports/scheduling.vue` → `/reports/scheduling`

## Permissions

`billing.read`, `budgets.read`, `scheduling.read`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** _(none)_

module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/reports/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
