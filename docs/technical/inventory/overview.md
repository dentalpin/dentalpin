---
module: inventory
last_verified_commit: db2caa92
---

# inventory — overview

**Stock list with cost tracking, movement ledger, audit trail and
auto-deduction** (roadmap #220, core upgrade #226).

Per-item minimum quantities, atomic ``SELECT … FOR UPDATE`` row-locked
stock changes, an append-only ``stock_movements`` ledger (the audit
trail), ``unit_cost`` with a valuation endpoint, and automatic
deduction of linked consumables when a treatment is performed.

## What it is

Clinic-scoped CRUD over the `InventoryItem` list plus several special
endpoints:

- `POST /{item_id}/adjust` applies a **relative** stock change
  (`+delta` restock / `-delta` consumption) via a ``SELECT … FOR UPDATE``
  row lock followed by Python arithmetic floor check.
- `GET /valuation` returns the total on-hand value over items with a
  known `unit_cost`.
- `GET /{item_id}/movements` returns the full audit trail for one item —
  every quantity change ever applied, with reason, actor, and timestamp.

Concurrency (the PR #153 post-mortem): quantity changes are guarded at
the row level — a ``SELECT … FOR UPDATE`` lock serialises concurrent
adjustments, and a `CHECK (stock_quantity >= 0)` constraint backs every
path. Adjustments that would drive stock negative return `409`, and two
concurrent adjustments can neither go negative nor lose an increment.

## Audit trail

Every quantity change — opening stock, manual adjustments, absolute-set
corrections, auto-deductions — is recorded in the append-only
`stock_movements` ledger with reason, note, optional business reference
and actor. The ledger sums exactly to on-hand stock. Items with ledger
history can no longer be hard-deleted (409); they are deactivated
instead (`is_active`), and the list hides inactive rows by default.

## Auto-deduction

When a treatment is performed (`odontogram.treatment.performed`), the
`treatment_consumables` module handles the event via subscription
inversion (#226): it reads its own links table via ORM and calls
`InventoryService.apply_consumption` as a clean public primitive.
No raw SQL, no inspector guard, no fail-soft branch — inventory has
no knowledge of treatment_consumables.

Duplicate deductions for the same treatment are silently ignored via a
partial unique index on `stock_movements` (idempotency — at-least-once
bus contract per ADR 0019).

Underflowing deductions **clamp at zero** rather than failing: clinical
care must never be blocked by bookkeeping, and the movement records the
actually-applied delta for a truthful audit trail. Manual adjustments
still 409 on underflow.

## Low-stock model

Each item carries a `min_quantity` threshold. An item is low when
`stock_quantity <= min_quantity` (computed property on the model; also
filterable server-side via `?low_stock=true`). The
`inventory.low_stock` event fires once per not-low → low crossing:
on creation already at/below threshold, or on the first
update/adjustment that crosses it. No bundled subscriber — a future
notifications or procurement module subscribes without importing
inventory.

## Data model

- `inventory_items` — `id`, `clinic_id`, `name`, `category`
  (`consumables|equipment|office|other`, closed Literal set stored as
  `String(50)` so adding categories later is code-only),
  `unit`, `stock_quantity` numeric(12,2) with CHECK >= 0,
  `min_quantity` numeric(12,2), `unit_cost` numeric(12,2) nullable,
  `is_active` boolean, `notes` (nullable), `created_by` (nullable FK
  `users.id`), timestamps.
- `stock_movements` — append-only ledger: `id`, `clinic_id`,
  `inventory_item_id`, `delta` numeric(12,2), `reason` (initial/
  restock/consumption/adjustment/correction), `note`,
  `reference_type`/`reference_id` (loose business link),
  `created_by`, `created_at`. Partial unique index on
  (reference_type, reference_id, inventory_item_id) WHERE
  reason = 'consumption' for idempotent auto-deduction.

## Dependencies

`manifest.depends = []` — fully standalone. FKs point only at core
tables (clinics, users). The auto-deduction is handled by
`treatment_consumables` via subscription inversion (#226).

## Tenancy

Every query, mutation and agent tool filters by the caller's
`clinic_id`; cross-clinic access surfaces as 404.

## Lifecycle

`installable=True`, `auto_install=False` (activated from the module
admin UI), `removable=True`. Own Alembic branch (`inventory`) rooted on
core `"0001"`. Uninstall round-trip covered by
`test_uninstall_roundtrip.py`.
