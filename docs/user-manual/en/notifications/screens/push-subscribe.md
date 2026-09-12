---
module: notifications
screen: push-subscribe
route: /p/push/[token]
related_endpoints:
  - POST /api/v1/notifications/push/subscribe-tokens
  - GET /api/v1/notifications/public/push/subscribe/{token}
  - POST /api/v1/notifications/public/push/subscribe/{token}
related_permissions:
  - notifications.push.write
related_paths:
  - backend/app/modules/notifications/frontend/pages/p/push/[token].vue
---

# Push subscribe (patient)

Public consent page (no login — the single-use token is the auth).
Token minting is API-only for now (POST subscribe-tokens); the patient
opens the link, sees which clinic asks, and taps Enable. The browser registers
the service worker and redeems the token with its subscription.
Expired/used links show an invalid-link message with instructions to
ask the clinic for a new one.
