# recall_reminders module

Pure event glue connecting two upstream modules that already exist but
don't talk to each other: `recalls` (builds the call-back list, publishes
`RECALL_CREATED`, but "never sends" by its own design) and `notifications`
(a full delivery gateway with consent/template/channel resolution, but
nothing was calling it for recalls).

This module has no models, no API routes, no UI. It's one subscriber
function.

## What it does

Subscribes to `EventType.RECALL_CREATED`. When a recall is created, calls
`NotificationGateway.enqueue(notification_type="recall_reminder", ...)`
for that patient. All consent checking, channel selection (email / SMS /
WhatsApp, whichever the patient has opted into and the clinic has
configured), and template rendering happens inside the existing gateway,
unchanged — this module makes zero delivery decisions itself.

## Setup step required (one-time, no code)

`notifications` renders a `notification_type` by looking up a matching
`NotificationTemplate` row. There's no built-in `"recall_reminder"`
template, so **you need to create one** via the existing template UI
(Settings → Notifications → Templates → New). Until you do, recalls will
enqueue a message that gets silently marked `skipped` (visible in the
notifications log) — not an error, just nothing sent.

Available template variables (from the event payload): `reason`,
`due_month`.

## Dependencies

`manifest.depends = ["recalls", "notifications"]` — imports
`NotificationGateway` directly from `notifications.gateway` (a
synchronous call, not just a read of another module's table) and listens
for `recalls`' event. Legal under ADR 0002 / 0003 because both are
declared.

## Lifecycle

- `installable=True`, `auto_install=False` (no point installing before
  you've decided you want it and created the template), `removable=True`.
- No migrations — no models.
- Event subscription re-attaches on every boot (`__init__`), unregisters
  on uninstall. Same pattern as `verifactu`'s and `tasks`' event handlers.

## CHANGELOG

See `./CHANGELOG.md`.
