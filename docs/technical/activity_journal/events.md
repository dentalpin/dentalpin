# Subscribed events — inclusion rationale

The roadmap asks the journal to subscribe to "nearly every EventType".
Taken literally that is unsafe: every handler here declares `db`
(transactional, ADR 0019), and the bus raises `RuntimeError` when a
transactional handler receives an event published without a session.
So the subscription set was derived mechanically: an event qualifies
**only if every publish site across `app/` passes `db=db`**. This was
verified with an AST audit of all ~90 `event_bus.publish` callsites;
re-run it whenever adding events.

## Subscribed (all publishers are transactional)

| Namespace | Events |
| --- | --- |
| `appointment.*` | `scheduled`, `confirmed`, `checked_in`, `in_treatment`, `completed`, `cancelled`, `no_show` (the status-map publishes in `agenda/service.py` pass `db=db`) |
| `budget.*` | `sent`, `accepted`, `rejected`, `cancelled`, `renegotiated`, `superseded` |
| `invoice.*` | `sent` |
| `payment.*` | `allocated`, `refunded` |
| `patient.*` | `created`, `archived` |
| `recall.*` | `created` |
| `odontogram.*` | `treatment.performed` |
| `lab_order.*` | `status_changed` |
| `treatment_plan.*` | `treatment_added`, `treatment_removed`, `item_session_completed`, `budget_sync_requested` |
| `document.*` | `generated` |
| `staff_attendance.*` | `clocked` |

## Deliberately NOT subscribed

Two reasons, both hard constraints rather than choices:

1. **At least one publisher omits `db=`** (background task, gateway,
   cron or fire-and-forget path). A transactional subscription would
   raise `RuntimeError` and crash that flow:
   `appointment.updated/status_changed/cabinet_changed`,
   `agenda.visit_note_updated`, all `budget.viewed/expired/reminder_sent`,
   `invoice.issued/paid`, `payment.recorded`, `patient.updated/medical_updated`,
   `recall.completed/cancelled/snoozed`, `media.*`,
   `email.*`, `notification.*`, `copilot.*`, `migration.*`,
   `clinic.created`, `verifactu.record.rejected`,
   `periodontogram.snapshot.closed`,
   `treatment_plan.confirmed/closed/reactivated/status_changed/items_reordered/item_completed_without_note/treatment_completed`,
   legacy `odontogram.surface/tooth/condition` updates and the
   `clinical_notes.*` note events.

2. **Never published anywhere yet** (reserved constants):
   e.g. `appointment.no_show`-style placeholders aside — `budget.created`,
   `invoice.created/cancelled/voided/partial_paid`, `credit_note.issued`,
   `payment.voided`, `notification.queued/delivered/sent/failed`,
   `recall.due`, `tenant.resolved`, `treatment.completed`,
   `odontogram.condition.changed` (non-legacy), `document.archived`,
   `copilot.tool.invoked/budget.threshold_reached`. They gain meaning
   automatically once their first transactional publisher lands — add
   them to `_SUBSCRIBED` in `__init__.py` then.

If a future change makes one of the excluded events fully
transactional, subscribe to it in the same PR that changes the
publisher(s).

## Actor attribution

`events.py` extracts `actor_id` from the first matching payload key in
`_ACTOR_KEYS`. Besides the generic `user_id`/`actor_id`/`created_by`,
the list carries the `*_by` keys the subscribed publishers actually use
(`changed_by`, `performed_by`, `completed_by`, `refunded_by`,
`cancelled_by`, `resent_by`, `accepted_by`, `recommended_by`) — each
verified to hold a **user** id at its publish site (a `users.id` FK or
`ctx.user_id`). Keys that may point at a non-user entity
(`professional_id`) are deliberately excluded. When subscribing to a
new event, check what its payload calls the acting user and extend
`_ACTOR_KEYS` if needed.

Some payloads carry no user at all (`patient.created/archived`,
`appointment.scheduled`, `invoice.sent`, `budget.sent`,
`lab_order.status_changed`, `treatment_plan.treatment_added/removed/
budget_sync_requested`) — those rows stay unattributed until their
publishers start including one. All id parsing is fail-soft: a
malformed id degrades to `NULL` (the verbatim value is still in
`payload`) rather than aborting the publisher's transaction.
