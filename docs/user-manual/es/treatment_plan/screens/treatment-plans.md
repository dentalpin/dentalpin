---
module: treatment_plan
screen: list
route: /treatment-plans
related_endpoints:
  - DELETE /api/v1/treatment_plan/treatment-plans/{plan_id}
  - DELETE /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}
  - GET /api/v1/treatment_plan/treatment-plans
  - GET /api/v1/treatment_plan/treatment-plans/patient/{patient_id}
  - GET /api/v1/treatment_plan/treatment-plans/pipeline
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/complete
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/status
  - POST /api/v1/treatment_plan/treatment-plans
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/close
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/confirm
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/contact-log
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/generate-budget
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/items
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/link-budget
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/reactivate
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/reopen
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/sync-budget
  - PUT /api/v1/treatment_plan/treatment-plans/{plan_id}
  - PUT /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
  - treatment_plan.plans.confirm
  - treatment_plan.plans.close
  - treatment_plan.plans.reactivate
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatment-plans/index.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: b1b82f5
---

# Bandeja de planes

Bandeja de planes de tratamiento de la clínica. Se organiza en
**cinco pestañas** alineadas con la máquina de estados del plan,
más una vista de pipeline con la cola de seguimiento.

## De un vistazo

- **Pestañas por estado.** *Borradores* (sin confirmar), *Pendientes*
  (esperando aceptación del paciente), *Activos* (con tratamiento
  en curso), *Completados*, *Cerrados* (rechazado, expirado,
  cancelado, abandono u *otro*).
- **Pipeline.** Vista de bandeja agregada (`GET /pipeline`) con
  totales por columna y los planes que necesitan acción de recepción
  (pendientes sin contacto reciente, presupuesto sin enviar, etc.).
- **Búsqueda y filtros.** Buscar por paciente, título o número de plan;
  filtros por profesional asignado, fecha de creación y motivo de
  cierre.
- **Sincronización con presupuesto.** Cada plan tiene un
  presupuesto enlazado (o lo crea al confirmar). Los cambios en el
  plan se propagan al presupuesto por eventos snapshot — no hace
  falta editar el presupuesto a mano.
- **Notas clínicas.** Desde el issue #60, las notas no se guardan
  en el plan: se delegan al módulo `clinical_notes`. El plan solo
  registra ejecuciones.

## Encontrar un plan

1. Cambia de pestaña o entra a la pipeline.
2. Filtra por profesional, fecha o motivo de cierre si procede.
3. Pulsa una fila para abrir el [detalle](./treatment-plans_id.md).

## Crear un plan

> Requiere `treatment_plan.plans.write`.

1. Pulsa **Nuevo plan** (top derecha) → te lleva a
   `/treatment-plans/new`.
2. Selecciona paciente, profesional y añade tratamientos.

## Registrar un contacto

> Requiere `treatment_plan.plans.write`.

1. En la fila o en el detalle, usa **Registrar contacto** para
   anotar una llamada / WhatsApp / email a recepción.
2. Estos contactos alimentan la vista de pipeline para no perder
   planes que llevan demasiado tiempo sin actividad.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver bandeja, pipeline y detalle | `treatment_plan.plans.read` |
| Crear, editar, añadir ítems, registrar contactos | `treatment_plan.plans.write` |
| Confirmar (borrador → pendiente) | `treatment_plan.plans.confirm` |
| Cerrar un plan | `treatment_plan.plans.close` |
| Reactivar un plan cerrado | `treatment_plan.plans.reactivate` |

## Resolución de problemas

- **El plan está en pendiente pero el paciente ya aceptó.** El
  evento `budget.accepted` lo mueve a *activo* automáticamente. Si
  no lo ha hecho, comprueba que el presupuesto está realmente
  aceptado y que ambos módulos están instalados.
- **No encuentro un plan cerrado.** En la pestaña *Cerrados* filtra
  por *motivo de cierre*. Por defecto incluye todos.
- **No aparece el botón *Confirmar*.** Tu rol no tiene
  `treatment_plan.plans.confirm` o el plan ya está en pendiente o
  posterior.
