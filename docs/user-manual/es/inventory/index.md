---
module: inventory
last_verified_commit: 0000000
---

# Inventario

Gestión de stock de la clínica — artículos, categorías, cantidades y
alertas de stock bajo. Módulo independiente sin dependencias de otros
módulos.

Versión base únicamente. Seguimiento de costes, movimientos de stock
y deducción automática al completar citas llegarán en la mejora del
core de inventario (issue #226).

## Pantallas

- [Lista de inventario](./screens/index.md) — estadísticas del panel,
  alertas de stock bajo, lista de artículos con filtro por categoría y
  búsqueda, crear/editar/eliminar artículos y ajustes de stock atómicos.

## Referencia rápida

| Acción | Permiso requerido |
|--------|-------------------|
| Ver lista, panel y alertas de stock bajo | `inventory.read` |
| Crear, actualizar artículos, ajustar stock | `inventory.write` |
| Eliminar artículos (soft-delete) | `inventory.delete` |

## Módulos relacionados

- **Consumibles de tratamiento** (#225) — enlaza tratamientos del
  catálogo con artículos de inventario.
- **Mejora del core de inventario** (#226) — añade seguimiento de
  costes, movimientos de stock, pista de auditoría y deducción
  automática.
- **Proveedores y compras** (#227) — órdenes de compra, reabastecimiento
  y gestión de proveedores se construyen sobre este módulo.
