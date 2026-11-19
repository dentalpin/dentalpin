---
module: online_booking
screen: requests
route: /online-booking
related_endpoints:
  - GET /api/v1/online_booking/requests
  - POST /api/v1/online_booking/requests/{request_id}/accept
  - POST /api/v1/online_booking/requests/{request_id}/reject
  - GET /api/v1/patients
related_permissions:
  - online_booking.read
  - online_booking.write
  - agenda.appointments.write
  - patients.write
related_paths:
  - backend/app/modules/online_booking/frontend/pages/online-booking/index.vue
last_verified_commit: 0000000
---
# Solicitudes online

Revisa la fecha, el motivo y el estado de confirmación. Para aceptar una solicitud confirmada, busca y selecciona un paciente existente o introduce nombre y apellidos para crear uno. Recházala indicando un mensaje que se enviará por correo. Si el hueco ya está ocupado, actualiza la lista; si sigue pendiente, recházala y pide al paciente que envíe otra solicitud para el nuevo horario.
