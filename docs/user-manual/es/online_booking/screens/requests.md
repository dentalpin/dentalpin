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
last_verified_commit: f44dbd9
---
# Solicitudes online

El menú muestra el número de solicitudes confirmadas pendientes. Revisa la fecha, el motivo y el estado. Pulsa **Aceptar** en una solicitud confirmada para abrir el formulario. Para crear la cita, selecciona profesional, gabinete opcional y duración (se propone la configurada para el motivo). Selecciona un paciente existente entre las coincidencias de teléfono o email, búscalo, o crea uno revisando los datos prellenados y editables. Pulsa **Crear cita**.

Para rechazarla, escribe un mensaje que se enviará por correo. Si el hueco ya está ocupado, actualiza la lista; si sigue pendiente, recházala y pide al paciente que envíe otra solicitud para el nuevo horario.

Al crear y confirmar una solicitud se comprueban las citas y retenciones del profesional configurado; al aceptarla, las del profesional y el gabinete que elijas. La agenda permite crear o mover citas solapadas; si una cita posterior ocupa el hueco, la siguiente decisión de reserva rechazará el conflicto.

Los administradores pueden abrir **Ajustes de la página pública** para activar la reserva y configurar el profesional responsable, la URL, el intervalo de inicio, la ventana, el aviso mínimo y los motivos con nombre en español e inglés, duración, estado y orden. Desactiva los motivos que ya no ofreces para conservar las solicitudes antiguas. Sube un logo PNG, JPG o SVG (hasta 1 MB) o indica una URL HTTPS; la imagen subida tiene prioridad. Guarda antes de pulsar **Ver página pública**. Los festivos y cierres se gestionan en Horarios de la clínica, en Fechas especiales.
