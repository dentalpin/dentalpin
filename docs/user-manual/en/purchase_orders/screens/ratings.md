---
module: purchase_orders
screen: ratings
route: /procurement/ratings
last_verified_commit: 0f333000
related_endpoints:
  - GET /api/v1/supplier_ratings
  - POST /api/v1/supplier_ratings/reviews
  - PATCH /api/v1/supplier_ratings/reviews/{id}
  - DELETE /api/v1/supplier_ratings/reviews/{id}
related_permissions:
  - supplier_ratings.read
  - supplier_ratings.write
related_paths:
  - backend/app/modules/purchase_orders/frontend/pages/procurement/ratings/index.vue
---

# Ratings

Found under the **Ratings** sidebar entry. Each supplier card shows
order count, received count, on-time rate and rejection rate computed
from purchase order history, plus the current manual 1–5 score.

## What you can do

- **Rate** a supplier 1–5 with an optional comment (one rating per
  supplier; a second one is refused — edit instead).
- **Edit** or **delete** the manual rating. Metrics are derived live
  and cannot be edited.
