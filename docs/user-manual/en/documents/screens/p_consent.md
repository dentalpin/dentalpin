---
module: documents
screen: p_consent
route: /p/consent
last_verified_commit: 0000000
related_endpoints:
  - GET /api/v1/documents/public/consents/current
  - POST /api/v1/documents/public/consents/current/sign
related_paths:
  - backend/app/modules/documents/frontend/pages/p/consent/index.vue
---

# Tablet consent signature

Open the link supplied by the clinic on the tablet without a staff session. Read the text, select patient, guardian or representative, and enter your name. Draw the signature and confirm. The link expires after 30 minutes and accepts one signature. Revocation uses a separate link and signature.

Staff can display a QR code or copy the link to open it on the tablet. Unsigned previews are marked DRAFT; signed revocations are shown as revoked.
