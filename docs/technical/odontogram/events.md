---
module: odontogram
last_verified_commit: 50cce0f
---

# Odontogram — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

Two groups. The `odontogram.treatment.*` events are published via
`EventType`; the tooth-state events (`surface`/`tooth`/`condition`) use
the module-local `OdontogramEventType` class in `service.py` (kept for
the legacy surface/tooth update path).

| Event | When | Consumers |
|-------|------|-----------|
| `odontogram.treatment.performed` | A planned/charted treatment is marked performed | budget, patient_timeline, payments, periodontogram, treatment_plan |
| `odontogram.treatment.added` | Treatment added to a tooth | — |
| `odontogram.treatment.status_changed` | Treatment status transition | — |
| `odontogram.treatment.deleted` | Treatment removed | — |
| `odontogram.surface.updated` | A tooth surface condition changes | — |
| `odontogram.tooth.updated` | A whole-tooth condition changes | — |
| `odontogram.condition.changed` | A tooth condition is (re)assigned | — |

`odontogram.treatment.performed` feeds the payments earned ledger — its
payload carries the `unit_price`/`price_snapshot` the payments handler
needs. **`unit_price: null` means "revenue already attributed
elsewhere"**: `TreatmentService.perform(publish_price=False)` is how
treatment_plan finalizes a sessioned item whose amounts were already
booked per-session (`treatment_plan.item_session_completed`);
subscribers must not book revenue for a null price. See the module
`CLAUDE.md` for the full payload contract.

## Subscribed

_This module does not subscribe to any events_ (`get_event_handlers`
returns `{}`; plan→treatment propagation lives in
`TreatmentPlanService.complete_item`).

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, **after the DB commit succeeds**.
3. Add the row to the table above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.
