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

# Artículos de proveedor

En la entrada **Artículos de proveedor**. Cada fila enlaza un
proveedor con un artículo de inventario, con referencia y precio.

## Qué puedes hacer

- **Enlazar** un artículo con un proveedor (referencia y precio
  opcionales). Los enlaces alimentan la reposición: gana el preferido,
  si no el primero por nombre.
- **Deslistar** un enlace. Queda en el historial pero deja de usarse
  para sugerencias.
