---
module: payroll
screen: periods
route: /payroll/periods
last_verified_commit: 55144ef3
related_endpoints:
  - GET /api/v1/payroll/periods
  - POST /api/v1/payroll/periods
  - POST /api/v1/payroll/periods/{id}/status
  - DELETE /api/v1/payroll/periods/{id}
related_permissions:
  - payroll.read
  - payroll.write
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/periods/index.vue
---

# Períodos

En la entrada **Períodos** de la nómina (solo admin). Cada período
muestra su mes `AAAA-MM` con insignia borrador/cerrado/pagado; al
abrirlo ves sus movimientos.

## Qué puedes hacer

- **Abrir** un período escribiendo su mes `AAAA-MM` (solo si no existe
  ya uno para ese mes).
- **Cerrar** un borrador y luego **marcar como pagado** al liquidar —
  ambos piden confirmación. Los períodos cerrados y pagados son de
  solo lectura; las transiciones solo avanzan.
- **Eliminar** un período borrador vacío con confirmación (corrección
  de mes erróneo). Un período con movimientos se rechaza con error.
