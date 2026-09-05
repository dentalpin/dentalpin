---
module: payroll
last_verified_commit: 0f333000
---

# payroll — permissions

Returned by `PayrollModule.get_permissions()`
(relative names; the registry namespaces them as `payroll.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `payroll.read` | List and view profiles, periods, entries | `GET /api/v1/payroll/profiles`, `GET /api/v1/payroll/profiles/{id}`, `GET /api/v1/payroll/periods`, `GET /api/v1/payroll/periods/{id}`, `GET /api/v1/payroll/periods/{id}/entries`, `GET /api/v1/payroll/entries/{id}` |
| `payroll.write` | Create/edit profiles, periods, entries; transitions | `POST /api/v1/payroll/profiles`, `PATCH /api/v1/payroll/profiles/{id}`, `POST /api/v1/payroll/periods`, `POST /api/v1/payroll/periods/{id}/status`, `POST /api/v1/payroll/entries`, `PATCH /api/v1/payroll/entries/{id}` |
| `payroll.reports.read` | Read monthly/annual rollups | `GET /api/v1/payroll/reports/monthly`, `GET /api/v1/payroll/reports/annual` |

## Role assignment

Strictly admin (`*` wildcard). No other role holds payroll permissions
in v1 — bank/tax data keeps the blast radius on the admin role
(approved scope, issue #229).

See `backend/app/modules/payroll/__init__.py` for the canonical role table.
