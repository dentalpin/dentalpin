---
module: reports
last_verified_commit: 0000000
---

# Reports — permissions

Returned by `ReportsModule.get_permissions()`
(relative names; the registry namespaces them as `reports.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `reports.billing.read` | Billing summaries, overdue list, VAT, gaps | `GET /api/v1/reports/billing/summary`, `/billing/overdue`, `/billing/by-payment-method`, `/billing/by-professional`, `/billing/vat-summary`, `/billing/gaps` |
| `reports.budgets.read` | Budget summaries and breakdowns | `GET /api/v1/reports/budgets/summary`, `/budgets/by-professional`, `/budgets/by-treatment`, `/budgets/by-status` |
| `reports.scheduling.read` | Scheduling summaries and analytics | `GET /api/v1/reports/scheduling/*` |
| `reports.financial.read` | Outstanding aging buckets + issued trend (invoice axis only) | `GET /api/v1/reports/billing/aging`, `/billing/issued-trend` |
| `reports.patient_stats.read` | Patient demographics family (next) | reserved, no endpoints yet |
| `reports.operational.read` | Operational KPI family (next) | reserved, no endpoints yet |

## Role assignment

Admin wildcard; dentist reads billing/scheduling/financial/patient-stats/operational;
hygienist reads scheduling/operational; assistant reads scheduling;
receptionist reads billing/scheduling/financial/patient-stats.

See `backend/app/modules/reports/__init__.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/reports/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
