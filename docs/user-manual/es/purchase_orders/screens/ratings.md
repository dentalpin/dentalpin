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

# Valoraciones

En la entrada **Valoraciones**. Cada tarjeta muestra pedidos,
recibidos, puntualidad y rechazo calculados del historial, más la
nota manual 1–5 actual.

## Qué puedes hacer

- **Valorar** de 1 a 5 con comentario opcional (una por proveedor;
  la segunda se rechaza — edita en su lugar).
- **Editar** o **eliminar** la nota manual. Las métricas se calculan
  en vivo y no se editan.
