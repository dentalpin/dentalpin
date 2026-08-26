---
module: inventory
last_verified_commit: db2caa92
---

# inventory — events

## Emitted

### `inventory.low_stock`

Fired once per **not-low → low crossing**: when an item is created
already at/below its threshold, when the first update/adjustment crosses
it, or when an auto-deduction drives it to/below the threshold.
Repeated adjustments while still low do not re-fire. Constant:
`EventType.INVENTORY_STOCK_LOW`. Payload:

- `clinic_id`
- `item_id`
- `name`
- `category`
- `stock_quantity` (float)
- `min_quantity` (float)

## Transaction model

Published **inside** the creating/updating transaction — after flush,
before the caller's commit — with the publisher's session (`db=`) per
ADR 0019, so a future transactional subscriber (notifications,
procurement) sees the row and rolls back with it.

## Consumed (#226 core upgrade — subscription inversion)

### `odontogram.treatment.performed` → auto-deduction

This event is **no longer handled** by inventory.  It was moved to
`treatment_consumables` via subscription inversion (#226):
that module owns the links table, already depends on inventory (no
cycle), and calls `InventoryService.deduct_for_treatment` as a clean
public primitive.

**Why the inversion**: inventory's original handler used raw SQL + an
inspector guard to read another module's table — coupling that CI
cannot detect, with a fail-soft branch that would silently stop
deducting if the inspector call failed.  The new design eliminates
raw SQL, the inspector round-trip, and the fail-soft branch entirely:
the module that owns the table is the one that reads it.

`InventoryService.deduct_for_treatment` is a clean public primitive
that reads the `treatment_consumables` links table via inspector (soft
coupling — no manifest dependency), applies each quantity via
`_apply_movement` (``clamp_at_zero=True``), and returns the applied
deltas.  Duplicate deductions for the same treatment are silently
ignored via a partial unique index on `stock_movements`
(``uq_stock_movements_consumption_ref``) — idempotent at-least-once
bus contract per ADR 0019.

Underflowing deductions **clamp at zero** rather than failing: clinical
care must never be blocked by bookkeeping, and the movement records the
actually-applied delta for a truthful audit trail. Manual adjustments
still 409 on underflow.
