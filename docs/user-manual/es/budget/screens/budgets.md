---
module: budget
screen: list
route: /budgets
related_endpoints:
  - DELETE /api/v1/budget/budgets/{budget_id}
  - DELETE /api/v1/budget/budgets/{budget_id}/items/{item_id}
  - GET /api/v1/budget/budgets
  - GET /api/v1/budget/budgets/{budget_id}
  - GET /api/v1/budget/budgets/{budget_id}/history
  - GET /api/v1/budget/budgets/{budget_id}/pdf
  - GET /api/v1/budget/budgets/{budget_id}/pdf/preview
  - GET /api/v1/budget/budgets/{budget_id}/pdf/signed
  - GET /api/v1/budget/budgets/{budget_id}/signature
  - GET /api/v1/budget/budgets/{budget_id}/versions
  - POST /api/v1/budget/budgets
  - POST /api/v1/budget/budgets/{budget_id}/accept
  - POST /api/v1/budget/budgets/{budget_id}/accept-in-clinic
  - POST /api/v1/budget/budgets/{budget_id}/cancel
  - POST /api/v1/budget/budgets/{budget_id}/duplicate
  - POST /api/v1/budget/budgets/{budget_id}/items
  - POST /api/v1/budget/budgets/{budget_id}/reject
  - POST /api/v1/budget/budgets/{budget_id}/renegotiate
  - POST /api/v1/budget/budgets/{budget_id}/resend
  - POST /api/v1/budget/budgets/{budget_id}/send
  - POST /api/v1/budget/budgets/{budget_id}/send-reminder
  - POST /api/v1/budget/budgets/{budget_id}/set-public-code
  - POST /api/v1/budget/budgets/{budget_id}/unlock-public
  - PUT /api/v1/budget/budgets/{budget_id}
  - PUT /api/v1/budget/budgets/{budget_id}/items/{item_id}
related_permissions:
  - budget.read
  - budget.write
  - budget.admin
  - budget.renegotiate
  - budget.accept_in_clinic
related_paths:
  - backend/app/modules/budget/frontend/pages/budgets/index.vue
  - backend/app/modules/budget/router.py
last_verified_commit: a297ec1
---

# Listado de presupuestos

Cola operativa de presupuestos de la clínica. Desde aquí buscas
presupuestos por paciente o número, filtras por estado del flujo,
estado de cobro, validez y profesional asignado, ordenas y abres el
detalle para trabajar sobre cada uno.

## De un vistazo

- **Filtros con dos orígenes.** Estado, profesional, validez y rango
  de fechas se mandan al endpoint nativo `GET /budgets`. El filtro
  *Cobro* (impagado / parcial / cobrado) lo aporta el módulo de
  pagos: la página llama a `/payments/filters/budgets-by-status` y
  cruza los IDs.
- **Columna *Cobrado / Pendiente*** — la rellena `payments` por el
  slot `budget.list.row.payments`. Si desinstalas cobros la columna
  desaparece sin romper nada.
- **Validez** — *Vigentes*, *A punto de expirar* (próximos 7 días),
  *Expirados*. Si elijes *A punto de expirar* se setean
  `valid_until_after=hoy` y `valid_until_before=hoy+7`.
- **Buscar** — caja `?search=` aplica al número de presupuesto y al
  paciente. Los filtros viven en la URL: enlace compartido =
  filtros compartidos.
- **Versionado.** Cada renegociación crea una versión nueva sin
  borrar la anterior. El listado por defecto solo enseña la versión
  vigente.

## Buscar un presupuesto

1. Escribe número o paciente en la barra de búsqueda.
2. Combina con los filtros de estado o cobro para acotar.
3. Pulsa la fila para abrir el [detalle](./budgets_id.md).

## Crear un presupuesto

> Requiere `budget.write`.

1. Pulsa **Nuevo presupuesto**. Te lleva a `/budgets/new`.
2. Selecciona paciente y añade ítems del catálogo, descuentos e IVA.
   Ver [Nuevo presupuesto](./budgets_new.md).

## Acciones por fila

> Algunas acciones requieren permisos extra. Mira la columna de
> permisos abajo.

- **Descargar PDF** — del presupuesto en su estado actual.
- **Duplicar** — crea un nuevo borrador con los mismos ítems.
- **Cancelar / Borrar** — admin only. Solo se puede borrar un borrador
  que no use ningún plan de tratamiento; un presupuesto enviado o
  aceptado se cancela, y el de un plan se descarta reabriendo el plan.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Navegar y buscar, descargar PDF | `budget.read` |
| Crear, editar, enviar, duplicar | `budget.write` |
| Borrar | `budget.admin` |
| Renegociar (nueva versión) | `budget.renegotiate` |
| Aceptar en clínica (tablet con firma) | `budget.accept_in_clinic` |

## Resolución de problemas

- **El filtro *Cobro* no aparece.** El módulo `payments` no está
  instalado; el slot no se rellena.
- **Veo el aviso "resultados truncados".** El filtro *Cobro* cruza
  contra una respuesta limitada de cobros; afina por fechas o
  profesional para reducir el universo.
- **Un presupuesto recién renegociado no sale.** El listado muestra
  la versión vigente: la nueva versión está visible, la anterior
  queda en el historial accesible desde el detalle.
