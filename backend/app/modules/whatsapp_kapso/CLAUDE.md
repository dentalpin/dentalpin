# whatsapp_kapso module

WhatsApp delivery for the notifications gateway, via **Kapso** (a SaaS over the
Meta WhatsApp Cloud API). Community, installable/removable. The thin "wire":
adapter + signed webhook + connect/settings + template sync. All comms logic
(routing, consent, outbox, conversation) lives in `notifications`.

Issue #63. ADR 0016 (channel adapters), ADR 0017 (inbound/conversation).

## Public API

Routes at `/api/v1/whatsapp_kapso/`:

| Method | Path | Auth |
|---|---|---|
| GET/PUT | `/settings` | `whatsapp_kapso.settings.read` / `.write` |
| POST | `/templates/sync` | `whatsapp_kapso.settings.write` |
| POST | `/templates/map` | `whatsapp_kapso.settings.write` |
| POST | `/test` | `whatsapp_kapso.settings.write` |
| POST | `/webhook` | **PUBLIC** — per-clinic HMAC signature |

## Dependencies

`manifest.depends = ["notifications", "patients"]`. The ONLY cross-module
import is `app.modules.notifications.channels` + `notifications` services/gateway
(all in `depends`). `notifications` does NOT depend on this module — the adapter
registers into the runtime registry.

## Permissions

`whatsapp_kapso.settings.read`, `whatsapp_kapso.settings.write` (admin only).

## Channel adapter

`KapsoAdapter` (`adapter.py`) registers into `notifications.channels.channel_registry`
at **import time**; `uninstall()` unregisters it. `supports()` = an active
`WhatsappKapsoSettings` row exists. `send()` posts a template (HSM) or free-form
text (session) to Kapso and returns the `wamid` as `provider_message_id`.

## Webhook (trust boundary)

`POST /webhook` is public (auth is per-route; no global gate). It:
1. resolves the clinic by `phone_number_id` (NEVER trusts a payload clinic_id),
2. verifies `X-Webhook-Signature` = HMAC-SHA256(raw_body, clinic webhook_secret),
3. inbound → `NotificationGateway.resolve_patient_by_phone` (a number
   shared by several patients links none, #965) then
   `NotificationGateway.record_inbound_reply` (publishes
   `notification.reply_received`); status → `NotificationGateway.record_delivery_status`.
Idempotent on the Kapso `message.id` (the `dedup_key` unique index).

## Events

Emits none directly. Drives `notification.reply_received` / `notification.delivered`
through the notifications gateway. `patient_timeline` records replies.

## Secrets

`api_key` + `webhook_secret` are Fernet-encrypted at rest via
`app.core.email.encryption` (project-wide util). Never returned by the API.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch `whatsapp_kapso` (`wak_0001`). Round-trip uninstall test
  (`tests/modules/whatsapp_kapso/test_uninstall_roundtrip.py`) drops only
  `whatsapp_kapso_*`.

## Gotchas

- **Proactive WhatsApp ⇒ approved template (HSM).** Free-form only inside the
  patient's 24h session window (enforced by the gateway via `last_inbound_at`).
- **Templates use NAMED variables** matching the notification context keys
  (`{{patient_name}}`). Positional `{{1}}` templates need order mapping (v2).
- **Kapso is a data processor** ⇒ DPA + per-clinic WABA with Meta billing.
  Minimal PII in payloads; never clinical free text.

## Related ADRs

- `docs/adr/0016-channel-adapter-architecture.md`
- `docs/adr/0017-inbound-conversation.md`

## CHANGELOG

See `./CHANGELOG.md`.
