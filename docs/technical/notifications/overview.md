---
module: notifications
last_verified_commit: 0000000
---

# Notifications — technical overview

Central multi-channel notification gateway: templates, per-patient
channel preferences, clinic settings, delivery logs, and a single
`POST /send` entry point that resolves the channel per recipient.

## Channels

- **email** — via clinic SMTP settings (`/smtp-settings`, testable).
- **whatsapp** — opt-out prefs (`whatsapp_opt_in_at` consent trail).
- **sms** (roadmap #231 PR1) — `Channel.SMS`; resolves to
  `patients.phone` (E.164, single source of truth — no separate
  `sms_phone` column in v1). Text-only: no attachments. Opt-out like
  email/whatsapp: explicit `sms_enabled=False` blocks (even
  `force_send`); a missing prefs row means reachable.
  `sms_opt_in_at` mirrors the whatsapp consent trail.
  Per-clinic cost guard: `sms_daily_limit` (default 100/UTC day,
  `0` = blocked, skips and inbound rows don't consume). An exhausted
  cap behaves like an unreachable channel: with `fallback_enabled`
  the next connected channel takes the send, and only when none is
  viable is the row skipped with `sms_rate_limited`. Email/whatsapp
  are uncapped flat-rate transports. Delivery itself arrives with the `sms_gateway`
  module (pluggable providers); until then SMS resolves but has no
  transport backend.
- **push** (issue #63) — browser WebPush via `pywebpush` (async send,
  10 s timeout, 24 h TTL, 4 KB payload cap). One VAPID pair per
  deployment (`DENTALPIN_VAPID_PRIVATE_KEY`, env only). Patient flow:
  staff mints a single-use token
  (`POST /push/subscribe-tokens`, 24 h expiry); the patient opens
  `/p/push/<token>` and the browser redeems it with its subscription
  (`GET`/`POST /public/push/subscribe/<token>`, no auth — the token
  is the auth). 410/404 endpoints prune on send; logs show
  `push:<n>` recipients. Service worker: `frontend/public/push-sw.js`.

## API surface

- `DELETE /api/v1/notifications/templates/{template_id}`
- `GET /api/v1/notifications/logs`
- `GET /api/v1/notifications/preferences/patient/{patient_id}`
- `GET /api/v1/notifications/settings`
- `GET /api/v1/notifications/smtp-settings`
- `GET /api/v1/notifications/templates`
- `GET /api/v1/notifications/templates/{template_id}`
- `POST /api/v1/notifications/send`
- `POST /api/v1/notifications/smtp-settings/test`
- `POST /api/v1/notifications/templates`
- `POST /api/v1/notifications/test`
- `POST /api/v1/notifications/push/subscriptions`
- `POST /api/v1/notifications/push/subscribe-tokens`
- `GET /api/v1/notifications/public/push/subscribe/{token}`
- `POST /api/v1/notifications/public/push/subscribe/{token}`
- `PUT /api/v1/notifications/preferences/patient/{patient_id}`
- `PUT /api/v1/notifications/settings`
- `PUT /api/v1/notifications/smtp-settings`
- `PUT /api/v1/notifications/templates/{template_id}`

## Frontend

- `backend/app/modules/notifications/frontend/pages/settings/notifications.vue` → `/settings/notifications`

## Permissions

`templates.read`, `templates.write`, `preferences.read`, `preferences.write`, `logs.read`, `send`, `settings.read`, `settings.write`, `push.read`, `push.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** `appointment.cancelled`, `appointment.scheduled`, `budget.accepted`, `budget.sent`, `invoice.sent`, `patient.created`

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/notifications/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
