---
module: payroll
screen: periods
route: /payroll/periods
last_verified_commit: 55144ef3
related_endpoints:
  - GET /api/v1/payroll/periods
  - POST /api/v1/payroll/periods
  - POST /api/v1/payroll/periods/{id}/status
  - DELETE /api/v1/payroll/periods/{id}
related_permissions:
  - payroll.read
  - payroll.write
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/periods/index.vue
---

# Periods

Found under the **Periods** payroll sidebar entry (admin only). Each
period shows its `YYYY-MM` month with a draft/closed/paid badge;
opening one shows its entries.

## What you can do

- **Open** a period by typing its `YYYY-MM` month (only while no period
  exists for that month).
- **Close** a draft period, then **mark as paid** once settled — both
  ask for confirmation. Closed and paid periods render read-only;
  transitions move strictly forward.
- **Delete** an empty draft period with confirmation (wrong-month
  corrections). A period with entries refuses with an error.
