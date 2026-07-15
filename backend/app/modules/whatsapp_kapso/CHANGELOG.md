# Changelog — whatsapp_kapso module

## Unreleased

- i18n: add French locale (`fr.json`) with full UI coverage.

- feat: initial release. WhatsApp delivery for the notifications gateway via
  Kapso (Meta Cloud API). Community, installable/removable (issue #63).
- `KapsoAdapter` (template + free-form session sends) registered into the
  notifications channel registry at import time; unregistered on uninstall.
- Public signed `/webhook` (HMAC-SHA256 per clinic, resolved by
  `phone_number_id`): inbound → `record_inbound_reply`, status →
  `record_delivery_status`. Idempotent on the Kapso message id.
- Per-clinic credentials (`WhatsappKapsoSettings`) + template cache
  (`WhatsappKapsoTemplate`); secrets Fernet-encrypted. Alembic branch
  `wak_0001`.
- Template auto-sync from Kapso + type→template mapping written into
  `notification_templates` via the gateway's public seam.
- Frontend connect/settings layer (credentials, webhook URL, template sync +
  mapping, test send). i18n ES/EN.
