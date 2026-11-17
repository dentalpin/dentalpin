---
module: integrations
last_verified_commit: ab94969a
---

# Integrations — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

_This module does not publish any events._

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `patient.created` | `integrations.handlers.IntegrationsHandlers.on_patient_created` | Transactional — queues one `WebhookDelivery` row per active subscription listing this event, on the publisher's own session. All deliveries for this publish share one `event_id`. No network I/O; the scheduled `dispatch_outbox` tick sends it. |
| `appointment.completed` | `integrations.handlers.IntegrationsHandlers.on_appointment_completed` | Same shape — queues one `WebhookDelivery` per active subscription. Shared `event_id`. |
| `appointment.scheduled` | `integrations.handlers.IntegrationsHandlers.on_appointment_scheduled` | Phase 2. Same shape. Publisher: agenda/service.py (db=). |
| `appointment.cancelled` | `integrations.handlers.IntegrationsHandlers.on_appointment_cancelled` | Phase 2. Same shape. Publisher: agenda/service.py (db=). |
| `appointment.no_show` | `integrations.handlers.IntegrationsHandlers.on_appointment_no_show` | Phase 2. Same shape. Publisher: agenda/service.py (db=). |
| `budget.sent` | `integrations.handlers.IntegrationsHandlers.on_budget_sent` | Phase 2. Same shape. Publisher: budget/workflow.py (db=). |
| `budget.accepted` | `integrations.handlers.IntegrationsHandlers.on_budget_accepted` | Phase 2. Same shape. Publisher: budget/workflow.py (db=). |
| `budget.rejected` | `integrations.handlers.IntegrationsHandlers.on_budget_rejected` | Phase 2. Same shape. Publisher: budget/workflow.py (db=). |

## Deferred triggers (publish without db=)

These events exist in `EventType` but their publishers do not pass a
session (`db=`), so subscribing would violate ADR 0019. Fixing them
requires a publisher-side change, tracked as a follow-up:

- `invoice.issued` / `invoice.paid` — billing/service.py
- `payment.recorded` — payments/service.py

The transactional `patient.updated` event is not exposed as an integration webhook trigger.

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method with `db=session` (ADR 0019 guard).
3. Add a transactional handler to `handlers.py` and register it in
   `__init__.py.get_event_handlers()`.
4. Add the event to `SUPPORTED_EVENT_TYPES` in `triggers.py`.
5. Add a frozen sample payload `sample_payloads/<event>.json`.
6. Add the row to the table above.
7. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
