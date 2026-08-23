# Inventory module — technical overview

**Issue:** #220
**Status:** V1 (base version)
**Dependencies:** none (`depends: []`)

## Purpose

Standalone module for tracking clinic stock: items, categories, quantities, and low-stock alerts. The module is the foundation for later roadmap items (treatment_consumables #225, inventory core upgrade #226, supplier & procurement #227).

## Data model

| Table | Purpose |
|-------|---------|
| `inventory_categories` | Per-clinic grouping (e.g. "Consumibles", "Medicamentos") |
| `inventory_items` | Individual stock items with quantity, min_quantity, location, supplier |

## Key design decisions

### Race condition guard (issue #153)

Stock adjustments use an atomic SQL statement:

```sql
UPDATE inventory_items
SET quantity = quantity + :delta, updated_at = now()
WHERE id = :item_id AND clinic_id = :clinic_id
  AND quantity + :delta >= 0
RETURNING id
```

This serializes concurrent adjustments at the DB level. No application-level locking is used.

### Low-stock detection

Computed dynamically: `quantity <= min_quantity AND min_quantity > 0`. The `is_low_stock` column is denormalized for fast filtering and recomputed on every write.

### Soft delete

Items use `status = 'deleted'` rather than hard-delete. The default query excludes deleted items.

## Future evolution (deferred to #226)

- Cost tracking (purchase price, average cost)
- Stock movements (audit trail)
- Auto-deduction on appointment completion

## Frontend

Nuxt layer at `backend/app/modules/inventory/frontend/`:
- **Page:** `/inventory` — item list with category filter, low-stock toggle, create/edit/delete
- **Composable:** `useInventory.ts` — typed API client
- **Locales:** en, es, fr, pt, ta
- **Nav:** `nav.inventory` in sidebar, gated by `inventory.read`

## API surface

See `CLAUDE.md` for the full endpoint list.
