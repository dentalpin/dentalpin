---
module: integrations
last_verified_commit: d426572
---

# Integrations — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

_This module does not publish any events._

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `patient.created` | `integrations.handlers.IntegrationsHandlers.on_patient_created` | Transactional — queues one `WebhookDelivery` row per active subscription listing this event, on the publisher's own session. No network I/O; the scheduled `dispatch_outbox` tick sends it. |
| `appointment.completed` | `integrations.handlers.IntegrationsHandlers.on_appointment_completed` | Same shape as `on_patient_created` — queues one `WebhookDelivery` row per active subscription listing this event. |

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
