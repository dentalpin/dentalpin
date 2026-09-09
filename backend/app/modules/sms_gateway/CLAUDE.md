# sms_gateway module

SMS delivery for notifications via pluggable providers (issue #231,
PR2). Community, removable. Registers an `SmsGatewayAdapter` into the
notifications channel registry from `on_activate` — the only
cross-module dependency, declared in `manifest.depends`.

## What it does

Routes mounted at `/api/v1/sms_gateway/` (admin only).

- `GET    /settings` — masked provider config; `sms_gateway.settings.read`
- `PUT    /settings` — select provider, store credentials, toggle; `sms_gateway.settings.write`
- `GET    /providers` — registered wire backends (the settings UI offers only these)
- `POST   /test`     — dry-run honesty check (sends nothing); `sms_gateway.settings.write`

Unregistered provider names are a loud 422 on PUT (never a silent
dead-end at send time).

## Frontend layer (issue #392 review, admin only)

Settings page under Settings → Integrations (`registerSettingsPage`,
kapso pattern): provider select from `GET /providers`, sender number,
active toggle, Test button surfacing the `/test` honesty note.
10 layer locales; screen docs
`docs/user-manual/{en,es}/sms_gateway/screens/`.

## Data model

Single table `sms_gateway_settings` (one row per clinic):

- `provider` — backend key (`log` placeholder default; `twilio` later)
- `account_sid_encrypted` + `auth_token_encrypted` (Fernet Text)
- `from_number`, `is_active`

Migration `smg_0001_initial` on own Alembic branch (`sms_gateway`), no
`depends_on` (core-auth FK only — kapso pattern). `smg_0002` seeds the
18 system SMS template rows (channel `sms`, clinic NULL); downgrade
deletes exactly those rows by marker.

## Providers

`providers.py` holds the wire backends behind a tiny registry
(`register_provider` / `get_provider`). v1 ships `log` only: it records
the send in the server log and reports success so the outbox flow runs
end to end without spending money. Any other selected provider fails
honestly at send time ("not implemented in v1"); `/test` reports the
same without sending. Twilio lands as a new backend under the same
adapter — no adapter change needed. Inbound replies arrive with the
provider backend (future `record_inbound_reply` wiring).

## Dependencies

`manifest.depends = ["notifications"]` — imports the channel contract
(`ChannelAdapter` shape, `Channel`, `OutboundMessage`,
`AdapterResult`) and nothing else.

## Permissions

`sms_gateway.settings.read/write`. Granted to `admin` (`*`) only —
provider credentials are admin secrets.

## Events emitted / consumed

None of its own. Sends flow through the standard
`notification.queued / sent / failed / delivered` events with
`channel=sms`.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- `on_activate` registers the adapter; `uninstall` unregisters it
  (kapso pattern, issue #91).
- Roundtrip uninstall test: walking `sms_gateway@-1` down drops the
  settings table and the seeded template rows, nothing else.

## Gotchas

- **The placeholder must stay honest.** Any UI or doc that names the
  provider calls it "not sending" (log records only). Nobody may
  install this thinking SMS go out until a real backend lands.
- **Secrets encrypted at rest, masked in responses** (`has_*`
  booleans). No agent tools in v1.
- **Every query filters `clinic_id`.**

## CHANGELOG

See `./CHANGELOG.md`.
