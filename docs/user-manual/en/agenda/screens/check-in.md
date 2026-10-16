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
last_verified_commit: 693ea9f45713ec91219886dc89a1cf4d194d0e07
---

# QR check-in (patient page)

Public landing for a scanned appointment QR code or a mailed reminder
link. No account, no login — the token in the URL path is the entire
credential (single appointment).

## What the patient sees

- **Counter QR** (scanned in the clinic): checks in automatically.
- **Reminder link** (from an email/SMS reminder): shows a confirm
  button and only checks in on press, so mail-scanner pre-fetches can
  never check anyone in.
- **Checked in** on success. Re-scanning the same code simply
  confirms the current status.
- **Too early / check-in closed** when outside the appointment window
  (two hours before start until one hour after end), with the
  appointment time.
- **Invalid code** when the token is expired, forged, or mistyped,
  with a retry button.
