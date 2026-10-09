# Changelog — whatsapp_webhook module

## Unreleased

- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- feat(i18n): Arabic (`ar`) locale for the module's frontend layer.
- feat(#63): initial release — WhatsApp channel adapter delivering each
  notification as Stripe-style-signed JSON to a clinic-configured
  Zapier/Make/n8n hook. Settings page (URL, show-once signing secret with
  rotation, test delivery), SSRF-guarded target URL, own Alembic branch.
