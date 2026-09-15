---
module: treasury
screen: treasury
route: /treasury
last_verified_commit: 695eb0f9
related_endpoints:
  - GET /api/v1/treasury/accounts
  - POST /api/v1/treasury/accounts
  - PATCH /api/v1/treasury/accounts/{account_id}
  - DELETE /api/v1/treasury/accounts/{account_id}
  - GET /api/v1/treasury/accounts/{account_id}/entries
  - POST /api/v1/treasury/transfers
  - POST /api/v1/treasury/accounts/{account_id}/corrections
related_permissions:
  - treasury.read
  - treasury.write
related_paths:
  - backend/app/modules/treasury/frontend/pages/treasury/index.vue
---

# Treasury

Found under the **Treasury** sidebar entry (admin only). Each account
shows its derived balance (opening + signed movements, never stored).

## What you can do

- **Create** cash or bank accounts (names unique per clinic).
- **Transfer** between accounts — both legs share one operation and
  appear in both statements.
- **Correct** an account with a mandatory memo (audit trail, never
  silent edits).
