# sms_gateway module

SMS delivery for the `notifications` gateway, via a pluggable provider —
starts on a `"placeholder"` provider that logs every attempt instead of
actually sending, until a real one is picked and configured.

## Public API

Routes mounted at `/api/v1/sms-gateway/`.

- `GET   /sms-gateway/providers` — list available provider keys; `sms_gateway.settings.read`
- `GET   /sms-gateway/settings`  — current settings (secret never returned, only `has_api_key`); `sms_gateway.settings.read`
- `PATCH /sms-gateway/settings`  — update provider/credentials/active flag; `sms_gateway.settings.write`
- `GET   /sms-gateway/outbox`    — recent send attempts (sent/failed/skipped), for visibility while no real provider is wired up; `sms_gateway.settings.read`

## Dependencies

`manifest.depends = ["notifications"]` — registers `SmsAdapter` into
`notifications.channels.channel_registry` at import time (same pattern as
`whatsapp_kapso`).

## The pluggable provider pattern (this is the "ready for later" part)

All provider-specific logic lives in `providers.py`. To wire in a real
provider once you've researched pricing/reliability and picked one:

1. Add a class implementing `SmsProvider` (one method: `send`) to
   `providers.py`.
2. Register it in the `PROVIDERS` dict at the bottom of that file.
3. In Settings → SMS, pick the new provider name and fill in the API
   key / sender ID / base URL (all generic fields — the same three cover
   Twilio, most regional gateways, and most REST-based SMS APIs).

Nothing in `adapter.py`, `service.py`, `router.py`, the `notifications`
module, or the frontend needs to change. This was a deliberate design
choice per your request to keep the provider question genuinely open
until you've done that research.

## IMPORTANT — this module alone does not enable SMS

Unlike every custom module built before this one (Phases 1–5), this one
also requires three small patches to the **existing** `notifications`
module — adding SMS to its `Channel` enum, a consent column, and a
channel-selection branch in its gateway. See the Phase 6 install guide
for the exact patches. Those three edits are what actually let SMS be
selected as a delivery channel at all; this module is the adapter that
handles it once it's selectable.

## Permissions

`sms_gateway.settings.read`, `sms_gateway.settings.write`. Admin only —
this is connection/credentials configuration, not day-to-day clinical
work.

## Lifecycle

- `installable=True`, `auto_install=False` (does nothing useful until
  configured), `removable=True`.
- Migrations on the `sms_gateway` Alembic branch, chained off the core
  `0001` migration.
- On uninstall, the adapter is unregistered from the channel registry so
  the SMS channel silently has no handler (matches `whatsapp_kapso`'s
  uninstall behavior).

## CHANGELOG

See `./CHANGELOG.md`.
