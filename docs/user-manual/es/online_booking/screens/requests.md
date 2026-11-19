---
module: online_booking
screen: requests
route: /online-booking
related_endpoints:
  - GET /api/v1/online_booking/requests
  - GET /api/v1/online_booking/requests/count
  - GET /api/v1/online_booking/requests/{request_id}/patient-suggestions
  - POST /api/v1/online_booking/requests/{request_id}/accept
  - POST /api/v1/online_booking/requests/{request_id}/reject
  - GET /api/v1/patients
related_permissions:
  - online_booking.read
  - online_booking.write
  - agenda.appointments.write
  - patients.read
  - patients.write
  - agenda.appointments.read
  - agenda.cabinets.read
related_paths:
  - backend/app/modules/online_booking/frontend/pages/online-booking/index.vue
last_verified_commit: 0000000
---
# Solicitudes online

El menú muestra el número de solicitudes confirmadas pendientes. Revisa la fecha, el motivo y el estado. Para crear la cita, selecciona profesional, gabinete opcional y duración (se propone la configurada para el motivo). Selecciona un paciente existente entre las coincidencias de teléfono o email, búscalo, o crea uno revisando los datos prellenados y editables. Pulsa **Crear cita**.

Para rechazarla, escribe un mensaje que se enviará por correo. Si el hueco ya está ocupado, actualiza la lista; si sigue pendiente, recházala y pide al paciente que envíe otra solicitud para el nuevo horario.
