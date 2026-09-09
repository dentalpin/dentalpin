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

# Pedidos

En la entrada **Pedidos**. La lista muestra pedidos con estado, con
filtro; al abrir uno se ven sus líneas con cantidades pedidas y
recibidas.

## Qué puedes hacer

- **Crear** un borrador: proveedor, fecha prevista, notas y líneas
  (artículo, cantidad, precio).
- **Cambiar estado** de borrador a enviado a confirmado a cancelado.
  No hay "marcar recibido" manual: solo se recibe al completar todas
  las líneas con una entrega.
- **Recibir** una entrega: buenas y rechazadas por línea. Solo las
  buenas actualizan stock y completan; las rechazadas se registran
  pero la línea sigue abierta.
- **Descargar** el PDF del pedido desde la lista.
