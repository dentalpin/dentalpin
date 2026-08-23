---
module: inventory
screen: index
route: /inventory
related_endpoints:
  - GET /api/v1/inventory/
  - POST /api/v1/inventory/
  - GET /api/v1/inventory/{inventory_item_id}
  - PATCH /api/v1/inventory/{inventory_item_id}
  - DELETE /api/v1/inventory/{inventory_item_id}
  - POST /api/v1/inventory/{inventory_item_id}/adjust-stock
  - GET /api/v1/inventory/low-stock
  - GET /api/v1/inventory/stats/dashboard
  - GET /api/v1/inventory/categories
  - POST /api/v1/inventory/categories
related_permissions:
  - inventory.read
  - inventory.write
  - inventory.delete
related_paths:
  - backend/app/modules/inventory/frontend/pages/inventory/index.vue
  - backend/app/modules/inventory/frontend/composables/useInventory.ts
last_verified_commit: 0000000
---

# /inventory

Gestión de stock de la clínica — artículos, categorías, cantidades y
alertas de stock bajo. Versión base: sin seguimiento de costes ni
movimientos de stock todavía (véase el issue #226 para la mejora
del core).

## Permisos

- `inventory.read` — ver la lista, estadísticas del panel y alertas
  de stock bajo (`admin` y el resto de roles por defecto).
- `inventory.write` — crear, actualizar artículos y ajustar stock
  (solo `admin` por defecto).
- `inventory.delete` — eliminar artículos (soft-delete) (solo `admin`
  por defecto).

## Qué hace esta pantalla

- **Estadísticas del panel** — total de artículos, conteo de stock
  bajo, conteo de sin stock y cantidad total en la clínica.
- **Alertas de stock bajo** — los artículos que están por debajo o
  al nivel mínimo se muestran con una insignia de advertencia naranja.
- **Filtrar** la lista por categoría, toggle de solo stock bajo, y
  búsqueda (coincide con código, nombre o proveedor).
- **Añadir artículo** — abre un modal para código, nombre, categoría,
  cantidad inicial, cantidad mínima, unidad, ubicación, proveedor y
  descripción.
- **Ajustar stock** — acción por fila para sumar o restar cantidad
  con un motivo opcional. El ajuste es a nivel atómico en la BD
  (protección contra carrera del issue #153).
- **Editar / eliminar** por fila, restringido a `inventory.write` /
  `inventory.delete`.
- **Paginación** — la lista está paginada (por defecto 20 por página,
  máximo 200).
