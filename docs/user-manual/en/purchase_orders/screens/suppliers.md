---
module: purchase_orders
screen: suppliers
route: /procurement/suppliers
last_verified_commit: 0f333000
related_endpoints:
  - GET /api/v1/suppliers
  - POST /api/v1/suppliers
  - PATCH /api/v1/suppliers/{id}
  - DELETE /api/v1/suppliers/{id}
related_permissions:
  - suppliers.read
  - suppliers.write
related_paths:
  - backend/app/modules/purchase_orders/frontend/pages/procurement/suppliers/index.vue
---

# Suppliers

Found under the **Suppliers** sidebar entry. The list shows vendor
contacts for the clinic, ordered by name, with search, preferred-only
and inactive filters.

## What you can do

- **Create** a supplier with contact details plus website, payment
  terms, lead time in days and the preferred flag.
- **Edit** terms and contact details in place.
- **Delete** a supplier. Links to inventory items are kept for history;
  deleting a supplier with live links is refused with a conflict
  message — delist the links first.
