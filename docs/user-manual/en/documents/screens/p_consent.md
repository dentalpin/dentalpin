---
module: documents
screen: p_consent
route: /p/consent
last_verified_commit: 0b0731be
related_endpoints:
  - GET /api/v1/documents/public/consents/current
  - POST /api/v1/documents/public/consents/current/sign
related_paths:
  - backend/app/modules/documents/frontend/pages/p/consent/index.vue
---

# Tablet consent signature

Open the link supplied by the clinic on the tablet without a staff session. Read the text, select patient, guardian or representative, and enter your name. Enter your ID document (national ID card or passport number): it is required when you sign as a guardian or representative and optional when you are the patient. Use ASCII letters (A-Z), digits and the characters `-`, `.` or `/`, without spaces. Draw the signature and confirm. The link expires after 30 minutes and accepts one signature. Revocation uses a separate link and signature.

Staff can display a QR code or copy the link to open it on the tablet. An administrator must configure the public application URL as the first entry in `ALLOWED_ORIGINS`. Unsigned previews are marked DRAFT; signed revocations are shown as revoked.

The consent text can include headings, bold, italic and lists. It is displayed already formatted and printed the same way in the signed PDF.
