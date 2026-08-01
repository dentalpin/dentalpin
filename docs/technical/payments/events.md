---
module: payments
last_verified_commit: 9d3fac6
---

# Payments — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Consumers |
|-------|------|-----------|
| `payment.recorded` | A payment is registered | — |
| `payment.allocated` | An allocation is created or moved (create / reallocate) | — |
| `payment.refunded` | A refund is registered against a payment | billing (invoice status recompute) |

Payload shapes are documented in the module `CLAUDE.md`.

## Subscribed

| Event | Handler | Effect |
|-------|---------|--------|
| `odontogram.treatment.performed` | `payments/events.py::on_treatment_performed` | Upserts one `PatientEarnedEntry` with `source_session_id = NULL` for the event's `unit_price`. Skips when `unit_price` is `null` — that means the revenue was already attributed per-session (see below). |
| `treatment_plan.item_session_completed` | `payments/events.py::on_session_completed` | Upserts one `PatientEarnedEntry` per session, keyed on `(treatment_id, source_session_id)`. Replaced the legacy `treatment_plan.treatment_completed` subscription with the multi-session feature. |

**Exactly-once booking.** A treatment's price lands in the earned
ledger through exactly one of the two paths. Exclusivity is enforced by
the publishers, not reconciled here:

- Plan-driven completion: sessions book the money one by one; the
  finalizing `odontogram.treatment.performed` is published with
  `unit_price: null` (`perform(publish_price=False)`), so
  `on_treatment_performed` skips.
- Odontogram-first completion: the performed event carries the full
  price (NULL-session row); treatment_plan cancels the item's pending
  sessions so no session event can fire afterwards.

Idempotency is DB-level: the composite unique constraint
`uq_earned_treatment_session` dedupes session rows, and the partial
unique index `uq_earned_treatment_null_session` dedupes NULL-session
rows (plain unique constraints treat NULLs as distinct — `pay_0004`).

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
