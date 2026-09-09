---
module: payroll
screen: profiles
route: /payroll/profiles
last_verified_commit: 0b59a2a2
related_endpoints:
  - GET /api/v1/payroll/profiles
  - POST /api/v1/payroll/profiles
  - PATCH /api/v1/payroll/profiles/{id}
  - GET /api/v1/auth/users
related_permissions:
  - payroll.read
  - payroll.write
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/profiles/index.vue
---

# Profiles

Found under the **Profiles** payroll sidebar entry (admin only). The
list shows one card per staff profile with payment type, base amount,
currency and masked bank markers (`···1234` — plaintext never renders).

## What you can do

- **Create** a profile: pick the staff member from the clinic roster,
  set monthly/hourly terms, base amount and currency, optionally attach
  bank account and tax ID (write-only).
- **Edit** terms: replace-to-edit secrets — leave a secret input empty
  to keep the stored value, fill it to rotate. Deactivate via the
  active toggle instead of deleting.
