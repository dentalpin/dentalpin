---
module: treatment_plan
screen: detail
route: /treatment-plans/[id]
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
  - backend/app/modules/treatment_plan/frontend/pages/treatment-plans/[id].vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: 6c91240
---

# Detalle del plan de tratamiento

Vista del plan: cabecera con paciente, profesional y estado;
columna principal con los ítems (catálogo o tratamiento odontograma)
y columna lateral con presupuesto enlazado, ejecuciones y contactos.
Aquí se confirma, sincroniza con el presupuesto, marca ítems como
ejecutados y se cierra o reactiva.

## De un vistazo

- **Estado y chip.** El chip en la cabecera refleja el estado:
  `draft`, `pending`, `active`, `completed`, `closed`. Las acciones
  cambian según el estado.
- **Ítems** — añadir, reordenar, completar. Cada ítem referencia un
  ítem del catálogo y, opcionalmente, un tratamiento del odontograma.
  Al completar un ítem se publica
  `treatment_plan.treatment_completed` (con `treatment_category_key`
  para recalls).
- **Doctor por tratamiento.** Cada ítem lleva su propio
  `assigned_professional_id`. Los nuevos ítems heredan el doctor del
  plan. Pulsa el chip de color junto al nombre del tratamiento para
  asignar a otro profesional (p. ej. empaste por Dr. A, endodoncia
  por Dr. B). Cuando intervienen dos o más doctores en el plan, el
  color del chip deja visible la mezcla de un vistazo. El chip
  sigue editable mientras el ítem esté pendiente, incluso después
  de validar el plan y de que el presupuesto esté activo —
  reasignar es operativo y no cambia el acuerdo con el paciente.
  Al completarlo, el chip pasa a ser un indicador de solo lectura
  que sigue mostrando `assigned_professional_id` (el doctor
  responsable del tratamiento); marcarlo como completado puede
  hacerlo recepción o un admin en nombre del clínico, así que
  "quién pulsó Completar" no es la referencia del chart.
- **Presupuesto enlazado.** Botones **Generar presupuesto** /
  **Enlazar con presupuesto existente** / **Sincronizar** según el
  caso. El plan publica `treatment_plan.treatment_added /
  _removed / budget_sync_requested` para que `budget` mantenga el
  presupuesto al día.
- **Contactos** — historial de toques de recepción. Útil cuando el
  plan está en *pendiente* esperando aceptación.
- **Notas clínicas.** Pueden engancharse al plan desde el módulo
  `clinical_notes` (slot `patient.detail.clinical.notes`).

## Confirmar un plan

> Requiere `treatment_plan.plans.confirm`.

1. Sobre un plan en `draft`, pulsa **Confirmar**.
2. Se publica `treatment_plan.confirmed`. El plan pasa a `pending`.
3. Si no había presupuesto enlazado, **Generar presupuesto** crea
   uno nuevo en el módulo `budget`.

## Marcar ítems como ejecutados

> Requiere `treatment_plan.plans.write`.

1. En el ítem, pulsa **Marcar como hecho**.
2. Se publica `treatment_plan.treatment_completed`. `recalls` puede
   sugerir un próximo recall basado en `treatment_category_key`.
3. Para anotar una nota clínica en ese momento, usa el botón de
   *Añadir nota* (lo aporta `clinical_notes`).

## Tratamientos en varias sesiones

Algunos tratamientos del catálogo (p.ej. corona, endodoncia) tienen
una **plantilla de sesiones** con nombre e importe por paso. Al
añadirlos al plan se crea automáticamente una sesión por cada paso.

- El item muestra un chip **X/Y sesiones** con el progreso.
- Bajo el item aparece la lista de sesiones (icono ✓ por completada,
  círculo punteado por pendiente).
- Pulsa el check de cada sesión para marcarla realizada — publica
  `treatment_plan.item_session_completed` y `payments` registra una
  entrada de "trabajo realizado" por ese importe.
- El item se finaliza automáticamente al completar la última sesión
  pendiente (entonces se ejecuta el flujo legacy de cierre).
- **Solo se pueden completar sesiones con el plan *En curso*** (presupuesto
  aceptado). En planes borrador/pendientes el check no aparece y la API
  responde 400 — no se cobra nada antes de que el paciente firme.
- **Los descuentos del presupuesto llegan a las sesiones.** Al aceptar
  un presupuesto con descuento por línea o global, las sesiones
  pendientes se reescalan al importe con descuento (sin IVA) y el item
  muestra el precio de catálogo ~~tachado~~ junto al efectivo. Se cobra
  lo que se firmó.
- Cancela una sesión si no llegó a hacerse: no genera cobro.
- Si el tratamiento se marca realizado desde el **odontograma**, el
  cargo se registra completo por esa vía y las sesiones pendientes del
  item pasan a canceladas automáticamente — el total nunca se cobra
  dos veces.

## Cambiar el doctor del plan

> Requiere `treatment_plan.plans.write`.

1. Abre **Editar plan** y selecciona otro profesional.
2. Si hay tratamientos pendientes asignados al doctor anterior,
   aparece un confirm: *"¿Reasignar los tratamientos pendientes?"*.
3. Pulsa **Sí, reasignar pendientes** para mover todos los ítems
   pendientes que coincidían con el doctor anterior al nuevo en el
   mismo guardado. Los ítems con override explícito (otro doctor)
   y los completados no se tocan nunca.
4. Pulsa **No, dejar como están** si solo quieres cambiar el
   doctor del plan; los ítems mantienen su asignación.

## Cerrar o reactivar

> Cerrar requiere `treatment_plan.plans.close`. Reactivar requiere
> `treatment_plan.plans.reactivate`.

1. **Cerrar** — elige motivo: rechazado, expirado, cancelado,
   abandono u *otro*. Publica `treatment_plan.closed` con
   `closure_reason`.
2. **Reactivar** — vuelve al estado `draft`. Publica
   `treatment_plan.reactivated`. Al **volver a confirmar** se genera
   un presupuesto nuevo (el rechazado/caducado anterior queda como
   histórico y deja de bloquear el plan).
3. **Reactivación automática** — un plan cerrado por *rechazo del
   paciente* vuelve solo a *En curso* si el paciente acepta una nueva
   versión del presupuesto (botón *Reenviar* en el presupuesto).

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver detalle, ítems y contactos | `treatment_plan.plans.read` |
| Añadir/reordenar ítems, completarlos, registrar contactos | `treatment_plan.plans.write` |
| Confirmar (draft → pending) | `treatment_plan.plans.confirm` |
| Cerrar | `treatment_plan.plans.close` |
| Reactivar | `treatment_plan.plans.reactivate` |

## Resolución de problemas

- **Confirmé el plan pero el presupuesto no aparece.** Confirmar crea
  el borrador de presupuesto automáticamente; recarga la página. Si el
  plan ya tenía un borrador vivo, se reutiliza en vez de crear otro.
- **El plan aparece bloqueado.** Solo bloquean los presupuestos
  *enviados* o *aceptados* (son un contrato con el paciente). Un
  presupuesto cancelado, rechazado o caducado no bloquea: puedes
  seguir editando el plan.
- **Cancelé el presupuesto desde el módulo de presupuestos.** El plan
  vinculado en *pendiente* vuelve solo a *borrador* para que puedas
  editarlo y re-confirmarlo.
- **El paciente aceptó el presupuesto pero el plan sigue en
  pendiente.** Comprueba que el evento `budget.accepted` está
  fluyendo (el módulo `budget` ha de estar instalado y el
  presupuesto realmente aceptado). El handler
  `on_budget_accepted` lo mueve a *activo*.
- **No puedo borrar un ítem.** El ítem ya está marcado como hecho.
  Los ítems completados quedan como histórico.
- **No me deja completar un ítem.** Tu rol no tiene
  `treatment_plan.plans.write` — o el plan aún no está *En curso*
  (primero hay que aceptar el presupuesto).
