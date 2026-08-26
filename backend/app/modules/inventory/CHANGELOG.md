# Changelog — inventory module

## Unreleased

- feat(#131): German (de) locale for the module's frontend layer.

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
- **Auto-deduction** of linked consumables: transactional handler on
  `odontogram.treatment.performed` reads the treatment_consumables links
  and applies each quantity inside the publisher's transaction (ADR
  0019). Soft runtime coupling — no manifest dependency (would cycle);
  absent module degrades to a logged no-op. Underflow clamps at zero
  with the applied delta recorded.
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
