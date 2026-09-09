---
module: payroll
screen: period-detail
route: /payroll/periods/[id]
last_verified_commit: 55144ef3
related_endpoints:
  - GET /api/v1/payroll/periods/{id}
  - GET /api/v1/payroll/periods/{id}/entries
  - POST /api/v1/payroll/entries
  - PATCH /api/v1/payroll/entries/{id}
  - DELETE /api/v1/payroll/entries/{id}
related_permissions:
  - payroll.read
  - payroll.write
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/periods/[id].vue
---

# Detalle del período

Se abre desde un período de la lista de **Períodos**. Muestra la
insignia de estado y una fila por movimiento de empleado
(`bruto − deducciones = neto`).

## Qué puedes hacer

- **Añadir** un movimiento mientras el período es borrador: empleado,
  bruto, deducciones, neto y nota opcional. El formulario bloquea el
  guardado salvo que el neto sea bruto menos deducciones (si no, el
  backend devuelve 422).
- **Editar** importes o notas de un movimiento en borrador. Fuera de
  borrador las acciones desaparecen — lo cerrado y pagado es inmutable.
- **Eliminar** un movimiento en borrador con confirmación (corrección
  de usuario erróneo).
