---
module: inventory
last_verified_commit: 0000000
---

# Inventory

Clinic stock tracking — items, categories, quantities, and low-stock
alerts. Standalone module with no dependencies on other modules.

Base version only. Cost tracking, stock movements, and auto-deduction
on appointment completion come later in the inventory core upgrade
(issue #226).

## Screens

- [Inventory list](./screens/index.md) — dashboard stats, low-stock
  alerts, item list with category filter and search, create/edit/delete
  items, and atomic stock adjustments.

## Quick reference

| Action | Required permission |
|--------|---------------------|
| View list, dashboard, low-stock alerts | `inventory.read` |
| Create, update items, adjust stock | `inventory.write` |
| Soft-delete items | `inventory.delete` |

## Related modules

- **Treatment consumables** (#225) — links catalog treatments to
  inventory items.
- **Inventory core upgrade** (#226) — adds cost tracking, stock
  movements, audit trail, and auto-deduction.
- **Supplier & procurement** (#227) — purchase orders, reorder,
  and supplier management build on this module.
