---
module: notifications
last_verified_commit: 0000000
---

# Notifications — events

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

Published by the gateway (`gateway.py`) across the outbox lifecycle:

| Event | When |
|-------|------|
| `notification.queued` | A message is enqueued for delivery. |
| `notification.sent` | An adapter delivered the message. |
| `notification.failed` | A send attempt failed (will retry until `max_attempts`). |
| `notification.delivered` | Vendor webhook reports delivered/read. |
| `notification.reply_received` | Inbound reply logged (vendor webhook, Phase 2). |
| `email.sent` / `email.failed` | **Legacy, dual-published** for `channel=email` only, one release, so `patient_timeline` keeps working. |

## Subscribed

All seven are **transactional** (ADR 0019): they queue a `CommunicationMessage`
on the publisher's session inside a savepoint, and the outbox tick does the
sending. A rolled-back request queues nothing (issue #183).

| Event | Handler | Effect |
|-------|---------|--------|
| `appointment.scheduled` | `handlers.on_appointment_scheduled` | Enqueue `appointment_confirmation`. |
| `appointment.cancelled` | `handlers.on_appointment_cancelled` | Enqueue `appointment_cancelled`. |
| `patient.created` | `handlers.on_patient_created` | Enqueue `welcome`. |
| `budget.sent` | `handlers.on_budget_sent` | Enqueue `budget_sent` (only when `send_method` is `email` or `whatsapp`; staff pick is honoured exactly). |
| `budget.accepted` | `handlers.on_budget_accepted` | Enqueue `budget_accepted`. |
| `budget.reminder_sent` | `handlers.on_budget_reminder_sent` | Enqueue `budget_reminder` with the public quote link (#287 bug 7). |
| `invoice.sent` | `handlers.on_invoice_sent` | Enqueue `invoice_sent` (only when `send_method` is `email` or `whatsapp`). |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method after `flush()` — the bus runs handlers
   inline, *before* the request commits. Pass `db=db` so transactional
   subscribers can join the transaction (ADR 0019, issue #183).
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
