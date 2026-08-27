---
module: notifications
screen: notifications
route: /settings/notifications
related_endpoints:
  - DELETE /api/v1/notifications/templates/{template_id}
  - GET /api/v1/notifications/logs
  - GET /api/v1/notifications/preferences/patient/{patient_id}
  - GET /api/v1/notifications/settings
  - GET /api/v1/notifications/smtp-settings
  - GET /api/v1/notifications/templates
  - GET /api/v1/notifications/templates/{template_id}
  - POST /api/v1/notifications/send
  - POST /api/v1/notifications/smtp-settings/test
  - POST /api/v1/notifications/templates
  - POST /api/v1/notifications/test
  - PUT /api/v1/notifications/preferences/patient/{patient_id}
  - PUT /api/v1/notifications/settings
  - PUT /api/v1/notifications/smtp-settings
  - PUT /api/v1/notifications/templates/{template_id}
related_permissions:
  - notifications.templates.read
  - notifications.templates.write
  - notifications.preferences.read
  - notifications.preferences.write
  - notifications.logs.read
  - notifications.send
  - notifications.settings.read
  - notifications.settings.write
related_paths:
  - backend/app/modules/notifications/frontend/pages/settings/notifications.vue
last_verified_commit: 0000000
---

# /settings/notifications

> _Scaffolded stub — replace with proper documentation when this module is next touched._

_Screen `/settings/notifications` of the `notifications` module._

## Permissions

- `notifications.templates.read`
- `notifications.templates.write`
- `notifications.preferences.read`
- `notifications.preferences.write`
- `notifications.logs.read`
- `notifications.send`
- `notifications.settings.read`
- `notifications.settings.write`

## What this screen does

Clinic-wide notification configuration.

### Channels (#287)

The **Channels** card at the top decides which wire the clinic talks to
patients on:

- **Preferred channel** — Email or WhatsApp; every automatic message
  (booking confirmation, reminder, welcome, quote accepted, …) goes out
  on this channel first. WhatsApp is selectable only once the Kapso
  integration is connected for the clinic.
- **Fallback** — when the preferred channel cannot deliver (no phone,
  no approved WhatsApp template), try the other configured channel
  instead of silently skipping.
- **Send buttons** — which manual Send buttons the rest of the app
  shows (appointment, quote, invoice). At least one is required.

### Message types

The per-type table controls which events notify at all
(enabled / auto-send / hours-before). It includes invoice sent, quote
reminders (7/14 days) and recall reminders.

