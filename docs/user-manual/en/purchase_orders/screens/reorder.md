---
module: purchase_orders
screen: reorder
route: /procurement/reorder
last_verified_commit: 0f333000
related_endpoints:
  - GET /api/v1/inventory_reorder/suggestions
  - POST /api/v1/inventory_reorder/orders
related_permissions:
  - inventory_reorder.read
  - inventory_reorder.write
related_paths:
  - backend/app/modules/purchase_orders/frontend/pages/procurement/reorder/index.vue
---

# Reorder

Found under the **Reorder** sidebar entry. The table shows computed
suggestions: 90-day usage, daily rate, chosen supplier and lead time,
stock on hand, quantity already on open orders, reorder point and the
suggested quantity.

## What you can do

- **Select** suggestions and generate draft purchase orders — one per
  supplier. The result lists the created drafts.
- Only items with recent usage, a vendor link and stock below the
  reorder point appear. An empty table means nothing needs ordering,
  not an error.
