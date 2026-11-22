---
module: whatsapp_kapso
screen: connect
route: /settings/integrations/whatsapp-kapso
related_endpoints:
  - GET /api/v1/whatsapp_kapso/settings
  - PUT /api/v1/whatsapp_kapso/settings
  - POST /api/v1/whatsapp_kapso/templates/sync
  - POST /api/v1/whatsapp_kapso/templates/map
  - POST /api/v1/whatsapp_kapso/test
last_verified_commit: f70d47ff
---

# Connect WhatsApp (Kapso)

Page at **Settings → Integrations → WhatsApp (Kapso)** (admins only).

## Steps

1. **Credentials.** Paste your Kapso *API key*, the *Phone number ID* and
   *Business account ID* of your connected number, and the *webhook secret*.
   Save. Secrets are stored encrypted and never shown again. A *Phone number
   ID* that another clinic has already connected is refused, so double-check
   it if saving fails.
2. **Webhook.** Copy the webhook URL shown on the page and paste it into your
   Kapso project's webhook settings, so DentalPin receives delivery statuses and
   patient replies.
3. **Templates.** Click *Sync* to fetch your Meta-approved templates, then map
   each notification type (e.g. "appointment reminder") to an approved template.
4. **Test.** Send a test message to a number to verify the connection.

## Replying to a patient

When a patient messages over WhatsApp, it appears on the **timeline** and in the
conversation card on their record. You can reply in free text within the next
24h; after that you must use a template.
