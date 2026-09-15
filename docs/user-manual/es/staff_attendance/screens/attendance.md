---
module: staff_attendance
screen: attendance
route: /attendance
last_verified_commit: a6660a00
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
- **Revisar** el listado de hoy y los totales por miembro; un fichaje
  abierto (sin pareja) se marca y se cuenta hasta ahora.
