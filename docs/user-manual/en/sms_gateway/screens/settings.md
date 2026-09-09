---
module: sms_gateway
screen: settings
route: /settings/integrations/sms-gateway
last_verified_commit: 0b59a2a2
related_endpoints:
  - GET /api/v1/sms_gateway/settings
  - PUT /api/v1/sms_gateway/settings
  - GET /api/v1/sms_gateway/providers
  - POST /api/v1/sms_gateway/test
related_permissions:
  - sms_gateway.settings.read
  - sms_gateway.settings.write
related_paths:
  - backend/app/modules/sms_gateway/frontend/components/SmsGatewaySettingsPage.vue
---

# SMS gateway

Found under **Settings → Integrations → SMS gateway** (admin only).
One provider configuration per clinic; without a saved active row,
SMS stays unavailable everywhere.

## What you can do

- **Pick the provider** from the backends actually registered
  server-side (v1 ships the `log` placeholder only). Unknown names
  are rejected with 422 — an unimplemented backend can never be
  selected.
- **Set the sender number** and **toggle** the provider active.
- **Test**: dry-run honesty check that reports what WOULD happen
  without sending anything. The bundled provider loudly records
  messages in the server log instead of sending — never install this
  thinking texts go out until a real backend lands.
