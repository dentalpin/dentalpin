---
module: staff_attendance
screen: attendance
route: /attendance
last_verified_commit: c3a21e8f65cbef6fc5e97a025a86c5474f19cd76
related_endpoints:
  - POST /api/v1/staff_attendance/events
  - GET /api/v1/staff_attendance/members
  - GET /api/v1/staff_attendance/events
  - GET /api/v1/staff_attendance/status/{user_id}
  - GET /api/v1/staff_attendance/report
related_permissions:
  - staff_attendance.read
  - staff_attendance.write
related_paths:
  - backend/app/modules/staff_attendance/frontend/pages/attendance/index.vue
---

# Asistencia

En la entrada **Asistencia** de la barra lateral. Registra entradas y
salidas del personal, consulta los fichajes de hoy y el informe diario.

## Qué puedes hacer

- **Fichar** a cualquier miembro de la clínica (incluido el flujo de
  recepción). Repetir el mismo fichaje devuelve 409 — las
  correcciones se hacen con un fichaje opuesto posterior, nunca
  reescribiendo.
- **Revisar** el listado de hoy y los totales por miembro, agrupados
  por el día local de la clínica. Cada línea muestra la hora del
  fichaje. Un fichaje abierto (sin pareja) se
  marca y se cuenta hasta ahora, nunca más allá del fin del día
  informado; un turno nocturno cuenta en el día en que termina.
