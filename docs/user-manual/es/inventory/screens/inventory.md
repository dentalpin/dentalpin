---
module: inventory
screen: inventory
route: /inventory
related_endpoints:
  - GET /api/v1/inventory/
  - GET /api/v1/inventory/{item_id}
  - POST /api/v1/inventory/
  - PATCH /api/v1/inventory/{item_id}
  - POST /api/v1/inventory/{item_id}/adjust
  - GET /api/v1/inventory/{item_id}/movements
  - GET /api/v1/inventory/valuation
  - DELETE /api/v1/inventory/{item_id}
related_permissions:
  - inventory.read
  - inventory.write
related_paths:
  - backend/app/modules/inventory/router.py
  - backend/app/modules/inventory/frontend/pages/inventory/index.vue
last_verified_commit: 76e5f4df
---

# Lista de inventario

## Qué hace esta pantalla

- **Filtrar** por categoría (con opción «Todas las categorías» para
  limpiar el filtro) y activar **solo stock bajo** (`stock <= min`).
- **Añadir artículo**: modal con nombre, categoría, unidad, stock
  inicial, mínimo, coste unitario y notas opcionales.
- **Ajustes rápidos +/-** por fila: cada pulsación es un cambio atómico
  en el servidor; un ajuste que llevaría el stock por debajo de cero se
  rechaza con `409`.
- **Ajuste en cantidad arbitraria**: pulsar la cifra de stock abre un
  campo para aplicar un delta (+/-) de cualquier tamaño, con motivo
  (reposición / consumo / ajuste / corrección) y nota opcional, por la
  misma vía atómica.
- **Editar artículo**: abre el mismo modal precargado, incluido el
  coste unitario usado por la valoración (la asignación absoluta de
  cantidad, p. ej. tras un recuento manual, se registra como corrección
  en el libro).
- **Movimientos**: el botón del ojo por fila abre la pista de auditoría
  del artículo: cada cambio de cantidad aplicado, del más reciente al
  más antiguo, con motivo y nota. Los artículos con historial no se
  pueden eliminar; desactívalos editándolos.
- **Insignia de valor**: valor total en mano de los artículos con coste
  conocido.
- **Eliminar** con confirmación (bloqueado si ya tiene movimientos).
- **Paginación** en servidor, 20 filas por página.

## Insignia de estado

Cada fila muestra `OK` o `Bajo` según si el stock actual ha alcanzado
el mínimo.
