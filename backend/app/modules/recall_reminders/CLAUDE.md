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

Transactional (ADR 0019): the handler declares a `db` parameter, so it
runs inside `recalls`' own publish transaction (`recalls/service.py`
passes `db=db` to `event_bus.publish`), inside a savepoint. A recall
that never actually commits enqueues no reminder — no confirmation for
something that was never booked (issue #183). Nothing is sent inside
the transaction either; `NotificationGateway.dispatch_outbox` (the
scheduler tick) owns the network I/O.

## Template

Ships `backend/templates/email/{locale}/recall_reminder.html` for
en/es/fr/pt/ta — no setup step required. The `notification_templates`
DB table is a per-clinic *override* (create one there only if a clinic
wants custom wording); the shipped file is the system default,
resolved automatically by `EmailService._render_template`'s
file-fallback when no DB row exists.

Available template variables (from the event payload, resolved inside
the handler): `patient_name`, `clinic_name`, `reason`,
`due_month` (humanized in the message's locale, e.g. `"September 2026"`
/ `"septiembre de 2026"`, not the raw `"2026-09-01"` from the payload;
the locale is the patient's `preferred_locale`, else the clinic's
communication language, the same order the gateway renders the template
in, #975). `reason` is still the stored code (`hygiene`, `checkup`, …).

## Dependencies

`manifest.depends = ["recalls", "notifications", "patients"]` — imports
`NotificationGateway` directly from `notifications.gateway` (a
synchronous call, not just a read of another module's table), reads
`Patient` (clinic-scoped) for the template context, and listens for
`recalls`' event. Legal under ADR 0002 / 0003 because all three are
declared.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- No tables of its own, but carries a single no-op Alembic revision
  (`rr_0001`, own branch, empty upgrade/downgrade) purely so
  `removable=True` has a self-contained branch to validate against —
  see `app/core/plugins/manifest_validator.py`'s
  `module_branch_is_isolated` check.
- Event subscription re-attaches on every boot (`__init__`), unregisters
  on uninstall. Same pattern as `verifactu`'s and `tasks`' event handlers.

## CHANGELOG

See `./CHANGELOG.md`.
