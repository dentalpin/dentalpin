---
module: payroll
screen: period-detail
route: /payroll/periods/[id]
last_verified_commit: 55144ef3
related_endpoints:
  - GET /api/v1/payroll/periods/{id}
  - GET /api/v1/payroll/periods/{id}/entries
  - POST /api/v1/payroll/entries
  - PATCH /api/v1/payroll/entries/{id}
  - DELETE /api/v1/payroll/entries/{id}
related_permissions:
  - payroll.read
  - payroll.write
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/periods/[id].vue
---

# Period detail

Opened from a period in the **Periods** list. Shows the period status
badge and one row per employee entry (`gross − deductions = net`).

## What you can do

- **Add** an entry while the period is draft: staff member, gross,
  deductions, net and an optional note. The form blocks saving unless
  net equals gross minus deductions (the backend returns 422 otherwise).
- **Edit** amounts or notes of a draft entry. Outside draft the actions
  disappear — closed and paid entries are immutable.
- **Delete** a draft entry with confirmation (wrong-user corrections).
