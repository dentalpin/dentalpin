# Changelog — inventory module

## Unreleased

- `InventoryService._apply_movement` renamed to `apply_movement`: it is the
  non-committing, row-locked entry point dependents use to move stock inside
  their own transaction (first consumer: `purchase_orders` receiving).

- fix(#226): auto-deduction idempotency — a duplicate delivery of the
  same treatment (same `reference_type`/`reference_id`/item) now bails
  in `InventoryService.apply_movement` **before** touching stock, so
  re-publishes are a true no-op (the partial unique index remains the
  concurrency backstop instead of the only guard). Previously the second
  delivery suppressed the movement row but still decremented the stock.

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

- feat(#131): German (de) locale for the module's frontend layer.
- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

## 0.2.0 — core upgrade (#226)

- **Stock movement ledger** (`stock_movements`, migration inv_0002 on
  the inventory branch): every quantity change — opening stock, manual
  adjustments, absolute-set corrections, auto-deductions — is recorded
  append-only with reason, note, business reference and actor. The
  ledger sums exactly to on-hand stock.
- **Audit trail semantics**: items with ledger history can no longer be
  hard-deleted (409); they are deactivated instead (`is_active`), and
  the list hides inactive rows by default.
- **Cost tracking**: `unit_cost` per item (create/edit/response) plus a
  `GET /inventory/valuation` endpoint totalling on-hand value over items
  with a known cost.
- **Auto-deduction** of linked consumables via subscription inversion
  (#226): `treatment_consumables` handles `odontogram.treatment.performed`,
  reads its own links table with its own ORM model, and calls
  `InventoryService.apply_consumption` as a clean public primitive.
  Duplicate deductions for the same treatment are silently ignored via
  a partial unique index (idempotent, at-least-once bus contract per
  ADR 0019). Underflow clamps at zero with the applied delta recorded.
- Adjustments now carry a reason (restock/consumption/adjustment/
  correction) and optional note; the actor is attributed from the
  request context. Agent tools gain reason/note and a new
  `get_stock_movements` READ tool.
- Frontend: valuation badge, unit-cost column + edit field, per-item
  movements modal, reason/note in the adjust popover; layer upgraded to
  seven locales (de/hu added).
- Migration inv_0002 (same branch); uninstall round-trip updated for
  both tables.

## 0.1.0 — initial release

- Standalone stock list: clinic-scoped item CRUD with categories
  (consumables / equipment / office / other), units, per-item minimum
  quantities and notes.
- Atomic stock adjustments (`POST /{id}/adjust`) guarded at the DB
  level — CHECK constraint plus a single-UPDATE floor guard — so
  concurrent changes can never drive stock negative (PR #153 race
  post-mortem, roadmap #220).
- Low-stock awareness: `is_low_stock` per item (`stock <= min`),
  SQL-level `?low_stock=true` filter, and an
  `inventory.low_stock` event fired transactionally (ADR 0019) on each
  not-low → low crossing.
- Server-side pagination; whole-team read+write by default.
- `auto_install=False`, `removable=True`; own Alembic branch with
  uninstall round-trip and tenant-isolation tests.
- Agent tools: `list_inventory_items`, `create_inventory_item`,
  `adjust_inventory_stock` (free-prose marked).
- Review follow-ups (PR #277): fixed sidebar icon (`i-lucide-package`),
  `nav.inventory` in de/hu host locales, low-stock-event crossing test,
  error/success toasts, labelled form fields, clearable category filter,
  translated category cells, trimmed quantity decimals, arbitrary-delta
  adjust popover, responsive column hiding on narrow screens; dropped
  the unused `reason` field from the adjust payload (no movements table
  until #226).
