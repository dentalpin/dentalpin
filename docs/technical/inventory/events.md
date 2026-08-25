---
module: inventory
last_verified_commit: 76e5f4df
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

## Consumed (#226 core upgrade)

### `odontogram.treatment.performed` → auto-deduction

Transactional handler (`db=`): deductions commit/rollback **with the
treatment performance itself**. Reads the `treatment_consumables` links
for the performed catalog item and applies each quantity as a
`consumption` movement referencing the treatment.

**Coupling decision** (the roadmap invited discussion): no manifest
dependency is declared. treatment_consumables already points DB-level
FKs *into* `inventory_items`, so declaring `depends:
["treatment_consumables"]` from this side would create a dependency
cycle. Instead the coupling is soft at runtime: presence of the links
table is checked via the inspector before reading, and absence degrades
to a logged no-op. Both modules stay installable in any order; the
deduction activates the moment both are installed.

Underflowing deductions **clamp at zero** rather than failing: clinical
care must never be blocked by bookkeeping, and the movement records the
actually-applied delta for a truthful audit trail. Manual adjustments
still 409 on underflow.

