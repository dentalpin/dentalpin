---
module: treasury
screen: treasury
route: /treasury
last_verified_commit: 6f1e970b
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
shows its derived balance (opening + signed movements, never stored),
formatted in the clinic's currency. Failed operations surface their
error instead of closing the modal silently.

## What you can do

- **Create** cash or bank accounts (names unique per clinic), with
  an optional opening balance.
- **Transfer** between accounts — both legs share one operation and
  appear in both statements.
- **Correct** an account with a mandatory memo (audit trail, never
  silent edits).
- **Deactivate** accounts you no longer use (reversible, from the
  statement header); deactivated accounts leave the transfer pickers.
- The statement shows dates and signed amounts on outgoing legs;
  negative balances render red (warning, never a block). Amounts
  accept a decimal comma (`25,50`, also `1.234,50`), and the transfer
  pickers list active accounts only. Correcting requires a memo (the
  button enables once you type it).
