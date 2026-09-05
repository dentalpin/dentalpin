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
  `0` = blocked, skips don't consume); email/whatsapp are uncapped
  flat-rate transports. Delivery itself arrives with the `sms_gateway`
  module (pluggable providers); until then SMS resolves but has no
  transport backend.

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
- `PUT /api/v1/notifications/preferences/patient/{patient_id}`
- `PUT /api/v1/notifications/settings`
- `PUT /api/v1/notifications/smtp-settings`
- `PUT /api/v1/notifications/templates/{template_id}`

## Frontend

- `backend/app/modules/notifications/frontend/pages/settings/notifications.vue` → `/settings/notifications`

## Permissions

`templates.read`, `templates.write`, `preferences.read`, `preferences.write`, `logs.read`, `send`, `settings.read`, `settings.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** `appointment.cancelled`, `appointment.scheduled`, `budget.accepted`, `budget.sent`, `invoice.sent`, `patient.created`

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/notifications/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
