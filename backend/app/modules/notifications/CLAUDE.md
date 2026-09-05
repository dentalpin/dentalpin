# Notifications module

Multi-channel notification **gateway**: our own communications logic
(channel resolution, consent, templates, outbox, logging) with pluggable
adapters that put a rendered message on the wire. Email ships built-in;
WhatsApp arrives via the `whatsapp_kapso` community module (Phase 2).
Heavy subscriber + now a publisher. See ADR 0016.

## Architecture

- `channels/` — the **public contract** vendor modules import:
  `ChannelAdapter` protocol, `OutboundMessage`/`AdapterResult`, `Channel`
  enum, and the idempotent `channel_registry` (pre-loads `EmailAdapter`).
  A vendor module `depends=["notifications"]` and calls
  `channel_registry.register(...)` from its `on_activate()` (ADR 0020 — never at import time, #325). The built-in EmailAdapter registers the same way from `NotificationsModule.on_activate`; the loader activates `notifications` before its vendors, so email is still always present first.
- `gateway.py` — `NotificationGateway.enqueue` (consent gate → channel
  resolution → persist `queued` row → publish) and `dispatch_outbox`
  (the scheduled sender, retry + backoff). **No network in a request.**
  SMS resolves like WhatsApp minus the Meta template gate (text-only,
  either message kind), gated by per-patient `sms_enabled` and a
  per-clinic `sms_daily_limit` (default 100/day, skips log
  `sms_rate_limited`).
- `service.py` — CRUD for templates/preferences/settings/SMTP + the
  `should_send_notification` consent check. No send path here anymore.
- Tables: `communication_messages` (outbox + audit), `notification_templates`,
  `notification_preferences`, `clinic_notification_settings`,
  `clinic_channel_settings`, `clinic_smtp_settings`.

## Public API

Routes mounted at `/api/v1/notifications/` (templates, preferences,
settings, logs).

## Dependencies

`manifest.depends = ["patients", "agenda", "budget", "billing"]`.

## Permissions

`notifications.send`,
`notifications.templates.{read,write}`,
`notifications.preferences.{read,write}`,
`notifications.settings.{read,write}`,
`notifications.logs.read`.

## Tools exposed

Agent tool in `tools.py` (wraps `NotificationGateway`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `send_notification` | WRITE | `NotificationGateway.enqueue` | `notifications.send` |

Structured params only (cloud-eligible under redaction). Enqueues through
the full consent path — never bypasses `do_not_contact`.

## Events emitted

- `notification.queued` / `notification.sent` / `notification.failed` /
  `notification.delivered` / `notification.reply_received`.
- `email.sent` / `email.failed` — **legacy, dual-published** for
  `channel=email` only, for one release, so `patient_timeline` keeps
  recording email comms until it migrates to the generic events.

## Events consumed

- `patient.created`
- `appointment.scheduled` / `appointment.cancelled`
- `budget.sent` / `budget.accepted` / `budget.reminder_sent`
- `invoice.sent`

## Lifecycle

- `removable=False`. Even when SMTP is disabled, the queue/logs surface
  is depended on by the audit feed.

## Gotchas

- **No outbound network calls during a request.** Sending is queued via
  `tasks.py` (APScheduler) so the request transaction can commit
  before the SMTP attempt.
- **Provider abstraction** lives behind `EMAIL_PROVIDER`. `console`
  prints to stdout — use it in dev.
- **Templates are i18n-aware** (Spanish UI strings). Never hardcode
  copy in handlers — use a template.
- **Locale resolution order**:
  1. Patient preference (``NotificationPreference.preferred_locale``).
  2. Clinic-wide default (``clinic.settings.communication_language``).
  3. ``DEFAULT_COMMUNICATION_LOCALE`` ("es") if neither is set.
  Encapsulated in ``service.resolve_clinic_communication_locale``.
  The clinic-wide setting is owned by this module — UI lives at
  ``/settings/communications/language`` (registered via
  ``frontend/plugins/settings.client.ts``).
- **Preferences are per-patient + per-event-type.** Honour them before
  enqueueing.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
