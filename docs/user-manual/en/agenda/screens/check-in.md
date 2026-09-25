---
module: agenda
screen: check-in
route: /p/check-in/[token]
related_endpoints:
  - POST /api/v1/agenda/public/check-in/{token}
related_permissions: []
related_paths:
  - backend/app/modules/agenda/frontend/pages/p/check-in/[token].vue
  - backend/app/modules/agenda/router.py
last_verified_commit: cf863c34c6bcf3ccfdfb5b1de38a03700ea44cbd
---

# QR check-in (patient page)

Public landing for a scanned appointment QR code. No account, no
login — the token in the URL path is the entire credential (valid 15
minutes, single appointment).

## What the patient sees

- **Checking in…** while the code is redeemed.
- **Checked in** on success. Re-scanning the same code simply
  confirms the current status.
- **Invalid code** when the token is expired, forged, or mistyped,
  with a retry button.
