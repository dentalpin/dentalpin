---
module: recalls
screen: list
route: /recalls
related_endpoints:
  - DELETE /api/v1/recalls/{recall_id}
  - GET /api/v1/recalls
  - GET /api/v1/recalls/export.csv
  - GET /api/v1/recalls/patients/{patient_id}
  - GET /api/v1/recalls/settings
  - GET /api/v1/recalls/stats/dashboard
  - GET /api/v1/recalls/suggestions/next
  - GET /api/v1/recalls/{recall_id}
  - GET /api/v1/recalls/{recall_id}/attempts
  - PATCH /api/v1/recalls/{recall_id}
  - POST /api/v1/recalls
  - POST /api/v1/recalls/{recall_id}/attempts
  - POST /api/v1/recalls/{recall_id}/cancel
  - POST /api/v1/recalls/{recall_id}/done
  - POST /api/v1/recalls/{recall_id}/link-appointment
  - POST /api/v1/recalls/{recall_id}/snooze
  - PUT /api/v1/recalls/settings
related_permissions:
  - recalls.read
  - recalls.write
  - recalls.delete
related_paths:
  - backend/app/modules/recalls/frontend/pages/recalls/index.vue
  - backend/app/modules/recalls/router.py
last_verified_commit: b40a1d2
---

# Lista de llamadas

Cola mensual de pacientes a contactar. Cada fila es un recall: a quién
llamar, por qué motivo, cuándo vence y en qué estado va. Está pensada
para que recepción la trabaje de arriba abajo: pulsar **Llamar**,
registrar el intento, mover el recall al siguiente estado.

## De un vistazo

- **Filtro por mes** — el selector arranca en el mes actual. La cola
  muestra los recalls cuyo `due_month` cae en el mes elegido.
- **Cuatro contadores arriba** — *Vencen esta semana*, *Vencidos*,
  *Programadas este mes*, *Tasa de conversión*. Se recalculan al
  cambiar cualquier filtro. La conversión es citas programadas /
  recalls vencidos del mes. *Vencen esta semana* cuenta los recalls
  abiertos con fecha exacta dentro de la semana actual, de lunes a
  domingo (hora de la clínica); los recalls solo con mes cuentan en el
  mes, no en la semana.
- **Filtros adicionales** — motivo, estado, prioridad y un
  conmutador *Vencidos*. Los filtros van en la URL: puedes guardar o
  compartir el enlace.
- **Estado por defecto:** *pendiente*. Los recalls *hechos*,
  *cancelados* o *necesita revisión* solo aparecen al cambiar el
  filtro de estado.
- **Exclusiones automáticas:** pacientes archivados o con
  `do_not_contact = true` no salen en la cola activa; sus recalls
  pasan a la cola **Necesita revisión**.
- **Exportar a CSV** — botón en la cabecera. Aplica los filtros
  activos.

## Trabajar un recall

> Requiere `recalls.write`.

1. Pulsa **Llamar** en la fila. Se abre un mini-popover con los
   teléfonos del paciente y los botones de resultado.
2. Selecciona el resultado: *No contesta*, *Programada*, *Rechaza*,
   *Hecho*. Cada uno registra un intento y mueve el recall al estado
   correspondiente.
3. Si el paciente acepta una cita, pulsa **Agendar cita** en la fila.
   La agenda se abre con el paciente preseleccionado y, al guardar,
   el recall se enlaza automáticamente y pasa a
   *contactado/programado*.

## Posponer o cerrar

> Requiere `recalls.write`.

1. Usa el menú **⋮** de la fila para acciones puntuales:
   - **Snooze N meses** — empuja `due_month` y deja el recall en
     pendiente. Se publica `recall.snoozed`.
   - **Hecho** — marca como completado. Publica `recall.completed`.
   - **Cancelar** — saca el recall de la cola activa. Publica
     `recall.cancelled`.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver lista, contadores y CSV | `recalls.read` |
| Llamar, snoozear, completar, enlazar cita | `recalls.write` |
| Editar ajustes (intervalos por motivo, mapa de categorías) | `recalls.write` |
| Borrar un recall | `recalls.delete` (solo admin por defecto) |

## Resolución de problemas

- **Un paciente con cita ya creada sigue en pendiente.** El auto-enlace
  solo dispara cuando hay **un único** recall activo que coincida. Si
  hay dos o más, enlázalo a mano desde la fila con **Agendar cita**.
- **Un paciente no aparece y debería.** Comprueba que no esté
  archivado o marcado con *No contactar* en su ficha — en ese caso su
  recall se ha movido a **Necesita revisión** (filtro de estado).
- **La conversión sale en cero.** El mes elegido aún no tiene recalls
  vencidos, o todos están aún pendientes.
