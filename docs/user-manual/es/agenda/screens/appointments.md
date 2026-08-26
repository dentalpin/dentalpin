---
module: agenda
screen: list
route: /appointments
related_endpoints:
  - DELETE /api/v1/agenda/appointments/{appointment_id}
  - DELETE /api/v1/agenda/cabinets/{cabinet_id}
  - GET /api/v1/agenda/appointments
  - GET /api/v1/agenda/appointments/{appointment_id}
  - GET /api/v1/agenda/appointments/{appointment_id}/cabinet-history
  - GET /api/v1/agenda/appointments/{appointment_id}/transitions
  - GET /api/v1/agenda/cabinets
  - GET /api/v1/agenda/kanban/day
  - PATCH /api/v1/agenda/appointment-treatments/{appointment_treatment_id}
  - PATCH /api/v1/agenda/appointments/{appointment_id}/cabinet
  - POST /api/v1/agenda/appointments
  - POST /api/v1/agenda/appointments/{appointment_id}/transitions
  - POST /api/v1/agenda/cabinets
  - PUT /api/v1/agenda/appointments/{appointment_id}
  - PUT /api/v1/agenda/cabinets/{cabinet_id}
related_permissions:
  - agenda.appointments.read
  - agenda.appointments.write
  - agenda.cabinets.read
  - agenda.cabinets.write
related_paths:
  - backend/app/modules/agenda/frontend/pages/appointments/index.vue
  - backend/app/modules/agenda/router.py
last_verified_commit: 0cce028b
---

# Citas

Calendario operativo de la clínica. Desde aquí ves las citas de la
semana o el día, las creas arrastrando sobre un hueco libre, las
mueves a otro profesional o gabinete y las haces avanzar por su
flujo (programada → confirmada → en sala → completada → cobrada).

## De un vistazo

- **Cuatro vistas** — semana, día y kanban en escritorio, y una vista
  móvil de un día simplificada en pantallas pequeñas. El selector
  vive en la cabecera, salvo en móvil donde solo existe la vista
  diaria.
- **Filtros por gabinete y profesional** — chips encima del
  calendario. Las citas sin gabinete asignado **siempre** se ven,
  para que recepción pueda arrastrarlas al gabinete que toque.
- **Drag, resize y arrastre entre días** — arrastra una cita a otra
  hora o profesional para moverla; arrastra su borde inferior para
  cambiarle la duración. Si solapa con otra del mismo profesional o
  gabinete, sale un aviso pero la operación se guarda.
- **Conflictos del backend** — si el servidor rechaza una cita por
  solape (HTTP 409) el calendario refresca la vista y muestra un
  *toast* de error; nada queda inconsistente.
- **Vista kanban del día** — las citas se agrupan por estado
  (programada, confirmada, en sala…). Sirve para que la consulta vea
  de un vistazo qué le toca a continuación.

## Crear una cita

> Requiere `agenda.appointments.write`.

1. En la vista semanal/diaria, pulsa o arrastra sobre un hueco libre.
   En kanban o móvil, pulsa **Nueva cita** o el botón flotante.
2. Selecciona paciente, motivo y duración. El profesional y el
   gabinete se preseleccionan según el hueco desde el que abriste el
   modal.
3. **Guardar**. Se publica el evento `appointment.scheduled` para que
   módulos como notificaciones puedan enviar la confirmación.

### Vincular tratamientos de un plan

En cuanto seleccionas paciente, el modal ofrece los tratamientos
pendientes de sus planes de tratamiento, para que la cita quede
agendada contra trabajo planificado real y no contra un motivo
escrito a mano.

- Los planes en **borrador**, **pendiente de aceptación** y
  **activo** ofrecen sus tratamientos. Un tratamiento ya realizado, o
  uno de un plan completado o cerrado, no se ofrece.
- Los tratamientos de un plan cuyo presupuesto el paciente todavía no
  ha aceptado llevan la etiqueta **Presupuesto sin aceptar** (icono de
  reloj de arena), tanto en el selector como en la lista de
  seleccionados. Agendarlos está permitido a propósito — las clínicas
  reservan la primera visita mientras el paciente decide — la
  etiqueta está para que recepción sepa que agenda por delante de la
  aceptación.
- El tratamiento solo se puede marcar como **realizado** cuando el
  presupuesto está aceptado y el plan activo; es ahí donde se imputa
  el dinero.
- Si el paciente no tiene ningún plan con tratamientos pendientes, el
  selector lo explica en lugar de mostrar un selector vacío.

## Mover o redimensionar

> Requiere `agenda.appointments.write`.

1. Arrastra la tarjeta a otra hora, día o profesional para mover.
2. Arrastra su borde inferior para cambiar la duración.
3. Si la nueva posición solapa con otra cita del mismo profesional o
   gabinete verás un aviso amarillo, pero la cita queda guardada. Si
   el backend rechaza la operación (HTTP 409 por una colisión más
   estricta), la vista se refresca y la cita vuelve a su posición
   original.

## Avanzar el estado

> Requiere `agenda.appointments.write`.

1. Abre la cita pulsando sobre ella.
2. En el panel de **Acciones rápidas** elige la siguiente transición
   disponible: *Confirmar*, *En sala*, *Completar*, *Cancelar*.
3. Al transicionar a **completada** aparece un modal de seguimiento
   con acciones de módulos hermanos (p. ej. *Programar recall*). El
   modal solo se muestra si hay módulos que lo aporten.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver calendario, abrir citas, ver historial de gabinete | `agenda.appointments.read` |
| Crear, mover, redimensionar, cancelar, transicionar | `agenda.appointments.write` |
| Ver los gabinetes (chips de filtro) | `agenda.cabinets.read` |
| Editar la nota clínica de la visita | `clinical_notes.notes.write` |

## Resolución de problemas

- **No veo el botón "Nueva cita".** Tu rol no tiene
  `agenda.appointments.write`.
- **No salen profesionales en el filtro.** Aún no hay miembros de la
  clínica con rol clínico activo. Crea o activa profesionales desde
  *Ajustes → Usuarios*.
- **Una cita movida vuelve a su sitio.** El backend rechazó el cambio
  con HTTP 409 (típicamente porque el profesional o el gabinete tiene
  otra cita en esa franja). Mira el *toast* de error y prueba otra
  hora.
- **El calendario solo va de 08:00 a 21:00.** El módulo `schedules`
  no está instalado o no tiene horario configurado; la agenda usa la
  ventana por defecto.
