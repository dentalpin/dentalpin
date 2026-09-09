---
module: purchase_orders
screen: items
route: /procurement/items
last_verified_commit: 0f333000
related_endpoints:
  - GET /api/v1/supplier_items
  - POST /api/v1/supplier_items
  - DELETE /api/v1/supplier_items/{id}
related_permissions:
  - supplier_items.read
  - supplier_items.write
related_paths:
  - backend/app/modules/purchase_orders/frontend/pages/procurement/items/index.vue
---

# Vendor items

Found under the **Vendor items** sidebar entry. Each row links one
supplier to one inventory item with the supplier SKU and price.

## What you can do

- **Link** an inventory item to a supplier (SKU and price optional).
  Links drive reorder sourcing: the preferred supplier wins, otherwise
  the first link by supplier name.
- **Delist** a link. It stays in history but is no longer sourced, so
  reorder suggestions stop considering that vendor for the item.
