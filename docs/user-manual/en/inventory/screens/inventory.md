---
module: inventory
screen: inventory
route: /inventory
related_endpoints:
  - GET /api/v1/inventory/
  - GET /api/v1/inventory/{item_id}
  - POST /api/v1/inventory/
  - PATCH /api/v1/inventory/{item_id}
  - POST /api/v1/inventory/{item_id}/adjust
  - GET /api/v1/inventory/{item_id}/movements
  - GET /api/v1/inventory/valuation
  - DELETE /api/v1/inventory/{item_id}
related_permissions:
  - inventory.read
  - inventory.write
related_paths:
  - backend/app/modules/inventory/router.py
  - backend/app/modules/inventory/frontend/pages/inventory/index.vue
last_verified_commit: 76e5f4df
---

# Stock list

## What this screen does

- **Filter** by category (with an "All categories" option to clear the
  filter) and toggle **low stock only** (`stock <= min`).
- **Add item** — modal with name, category, unit, initial stock,
  minimum threshold, unit cost and optional notes.
- **Quick +/- adjustments** per row — each click is an atomic server-side
  change; an adjustment that would drive stock below zero is rejected
  with `409`.
- **Arbitrary-size adjustment** — clicking the stock figure opens a
  field to apply a +/- delta of any size, with a reason (restock /
  consumption / adjustment / correction) and an optional note, through
  the same atomic path.
- **Edit item** — opens the same modal pre-filled, including the unit
  cost used by the stock valuation (absolute quantity set, e.g. after a
  manual count, is recorded as a correction in the ledger).
- **Movements** — the history icon per row opens the item's audit trail:
  every quantity change ever applied, newest first, with reason and
  note. Items with history cannot be deleted; uncheck them from active
  use by editing instead.
- **Stock value badge** — total on-hand value over items with a known
  unit cost.
- **Pagination** — server-side, 20 rows per page.

## Status badge

Each row shows `OK` or `Low` depending on whether current stock has
reached the minimum threshold.
