---
module: purchase_orders
screen: orders
route: /procurement/orders
last_verified_commit: 0f333000
related_endpoints:
  - GET /api/v1/purchase_orders
  - GET /api/v1/purchase_orders/{id}
  - POST /api/v1/purchase_orders
  - PATCH /api/v1/purchase_orders/{id}
  - POST /api/v1/purchase_orders/{id}/status
  - POST /api/v1/purchase_orders/{id}/receive
  - GET /api/v1/purchase_orders/{id}/receipts
  - GET /api/v1/purchase_orders/{id}/pdf
related_permissions:
  - purchase_orders.read
  - purchase_orders.write
related_paths:
  - backend/app/modules/purchase_orders/frontend/pages/procurement/orders/index.vue
---

# Purchase orders

Found under the **Purchase orders** sidebar entry. The list shows
orders with status badges, filterable by status; opening one shows its
lines with ordered vs received quantities.

## What you can do

- **Create** a draft order: supplier, expected date, notes and lines
  (item, ordered quantity, unit price).
- **Transition** draft to sent to confirmed to cancelled from the
  detail view. There is no manual "mark received": an order becomes
  received only when a delivery fulfils every line.
- **Receive** a delivery: enter good and rejected quantities per line.
  Only good units update stock and fulfil the line; rejected units are
  recorded but keep the line open for the replacement delivery.
- **Download** the order PDF from the list.
