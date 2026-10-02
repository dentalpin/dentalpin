---
module: payments
last_verified_commit: 2195ad0e
---

# Payments — permissions

Returned by `PaymentsModule.get_permissions()` (relative names
— the registry namespaces them as `payments.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `payments.record.read` | Listing payments, viewing payment details and refund logs, inspecting patient ledgers and pending charges, viewing budget allocations, fetching bulk budget and patient payment summaries, and querying payment status filter lists. | `GET /`, `GET /{payment_id}`, `GET /{payment_id}/refunds`, `GET /patients/{patient_id}/ledger`, `GET /patients/{patient_id}/pending-charges`, `GET /budgets/{budget_id}/allocations`, `POST /summary/by-budgets`, `POST /summary/by-patients`, `GET /filters/budgets-by-status`, `GET /filters/patients-with-debt`. |
| `payments.record.write` | Recording patient collections and reallocating payments across budgets or patient on-account credit balances. | `POST /`, `POST /{payment_id}/reallocate`. |
| `payments.record.refund` | Issuing payment refunds back to patients. | `POST /{payment_id}/refunds`. |
| `payments.reports.read` | Accessing payment reports including overview KPI summaries, method breakdowns, professional performance breakdowns, aging receivable debt analysis, refund audit logs, and collection trends over time. | `GET /reports/summary`, `GET /reports/by-method`, `GET /reports/by-professional`, `GET /reports/aging-receivables`, `GET /reports/refunds`, `GET /reports/trends`. |

## Role assignment

Declared in the module manifest
([`backend/app/modules/payments/__init__.py`](../../../backend/app/modules/payments/__init__.py)):

| Role          | Permissions                                                        | Notes |
|---------------|--------------------------------------------------------------------|-------|
| admin         | `*`                                                                | Full control over payment operations, refunds, and financial reporting. |
| dentist       | `record.read`, `record.write`, `record.refund`, `reports.read`     | Full clinical collection, reallocation, refund processing, and financial reporting. |
| hygienist     | `record.read`                                                      | View payment records and patient ledgers for clinical context. |
| assistant     | `record.read`, `record.write`                                      | Record patient collections and view ledgers chairside. |
| receptionist  | `record.read`, `record.write`, `reports.read`                      | Front-desk collections, reallocations, and payment report access; refunds restricted by default. |

See `backend/app/core/auth/permissions.py` for the canonical role
table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/payments/__init__.py`.
2. Add it to the role mapping in `manifest.role_permissions` (same
   file) so the appropriate roles can use it on a fresh install.
3. Wire the gate on the endpoint via
   `Depends(require_permission("payments.<name>"))`.
4. Mirror in `frontend/app/config/permissions.ts` under
   `PERMISSIONS.payments.*` so the UI can call
   `usePermissions().can(PERMISSIONS.payments.<name>)`.
5. Add a row to this file with the matching endpoints.
6. Re-run `python backend/scripts/generate_catalogs.py`.
