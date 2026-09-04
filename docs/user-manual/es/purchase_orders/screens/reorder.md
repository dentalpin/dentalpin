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

# Reposición

En la entrada **Reposición**. La tabla muestra sugerencias: consumo
de 90 días, tasa diaria, proveedor y plazo, stock, cantidad en pedidos
abiertos, punto de pedido y cantidad sugerida.

## Qué puedes hacer

- **Seleccionar** sugerencias y generar borradores — uno por
  proveedor. El resultado lista los creados.
- Solo aparecen artículos con consumo reciente, enlace y stock bajo el
  punto. Una tabla vacía significa que no hay nada que pedir.
