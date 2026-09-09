---
module: purchase_orders
---

# Compras

Proveedores, artículos de proveedor, pedidos, sugerencias de
reposición y valoraciones de la clínica. Las cinco entradas de Compras
comparten el mismo motor (#227): los proveedores y enlaces alimentan
las sugerencias, que generan borradores de pedido, cuyo historial
alimenta las valoraciones.

## Pantallas

- [Proveedores](./screens/suppliers.md): contactos, condiciones, preferido.
- [Artículos de proveedor](./screens/items.md): qué proveedor vende cada artículo.
- [Pedidos](./screens/orders.md): ciclo de vida, recepciones y PDF.
- [Reposición](./screens/reorder.md): sugerencias calculadas y borradores.
- [Valoraciones](./screens/ratings.md): métricas y notas manuales.
