---
module: billing
screen: list
route: /invoices
related_endpoints:
  - DELETE /api/v1/billing/invoices/{invoice_id}
  - DELETE /api/v1/billing/invoices/{invoice_id}/items/{item_id}
  - GET /api/v1/billing/invoices
  - GET /api/v1/billing/invoices/{invoice_id}
  - GET /api/v1/billing/invoices/{invoice_id}/history
  - GET /api/v1/billing/invoices/{invoice_id}/payments
  - GET /api/v1/billing/invoices/{invoice_id}/pdf
  - GET /api/v1/billing/invoices/{invoice_id}/pdf/preview
  - GET /api/v1/billing/patients/{patient_id}/summary
  - GET /api/v1/billing/series
  - GET /api/v1/billing/settings
  - PATCH /api/v1/billing/invoices/{invoice_id}/billing-party
  - POST /api/v1/billing/invoices
  - POST /api/v1/billing/invoices/from-budget/{budget_id}
  - POST /api/v1/billing/invoices/{invoice_id}/credit-note
  - POST /api/v1/billing/invoices/{invoice_id}/issue
  - POST /api/v1/billing/invoices/{invoice_id}/items
  - POST /api/v1/billing/invoices/{invoice_id}/payments
  - POST /api/v1/billing/invoices/{invoice_id}/send-email
  - POST /api/v1/billing/invoices/{invoice_id}/void
  - POST /api/v1/billing/series
  - POST /api/v1/billing/series/{series_id}/reset
  - PUT /api/v1/billing/invoices/{invoice_id}
  - PUT /api/v1/billing/invoices/{invoice_id}/items/{item_id}
  - PUT /api/v1/billing/series/{series_id}
  - PUT /api/v1/billing/settings
related_permissions:
  - billing.read
  - billing.write
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/index.vue
  - backend/app/modules/billing/router.py
last_verified_commit: 0000000
---

# Listado de facturas

Cola operativa de facturas: borradores en preparación, facturas
emitidas, abonos, anuladas. Desde aquí se buscan, filtran y abren
para emitir, enviar por email o anular.

## De un vistazo

- **Estados.** `draft` (borrador editable), `issued` (emitida — número
  fiscal asignado, ya no se puede editar), `paid` (cobrada total),
  `void` (anulada). Los abonos son un tipo de documento distinto
  (`credit_note`) que aparece junto con sus facturas relacionadas.
- **Numeración fiscal.** Solo al **emitir** la factura se asigna el
  número de la serie. Borrar un borrador no consume número; anular
  una emitida sí queda en el histórico.
- **Búsqueda y filtros.** Buscar por número, paciente o NIF.
  Filtros: estado, rango de fechas de emisión, serie y *con
  presupuesto*.
- **Cumplimiento.** Cuando el módulo `verifactu` está instalado,
  emitir una factura encola el envío a AEAT a través del *hook*
  asociado a `invoice.issued`. El estado de envío se ve en el
  detalle.

El distintivo **Histórica** identifica las facturas importadas. Sus totales siguen disponibles en el listado y en los informes de facturación, en la fecha de emisión original. Las facturas históricas quedan fuera de los resultados de vencidas.

## Encontrar una factura

1. Escribe número (`FACT-2026-####`), nombre del paciente o NIF en
   la búsqueda.
2. Aplica filtros: estado, serie, fechas.
3. Pulsa una fila para abrir el [detalle](./invoices_id.md).

## Crear una factura

> Requiere `billing.write`.

- **Desde presupuesto** — desde el detalle de un presupuesto
  aceptado, *Crear factura*. Pasa los ítems al borrador.
  [Ver factura desde presupuesto](./invoices_from-budget_budgetId.md).
- **Factura libre** — desde el listado **Nueva factura**.
  [Ver nueva factura](./invoices_new.md).

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Listar, buscar y descargar PDF | `billing.read` |
| Crear borradores, editar, emitir, enviar email, crear abonos | `billing.write` |
| Anular factura emitida | `billing.admin` |

## Resolución de problemas

- **No veo una factura recién creada.** Tu filtro activo la excluye.
  Quita filtros o busca por número.
- **No me deja editar.** La factura ya está emitida (`issued`). Para
  cambiar datos legales emite un abono (*Crear nota de crédito*) y
  factura de nuevo.
- **"Sin serie activa".** En *Ajustes → Series de facturación* no hay
  ninguna serie marcada como activa para el ejercicio. Activa o
  crea una.
