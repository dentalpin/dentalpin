---
module: budget
screen: detail
route: /budgets/[id]
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
  - backend/app/modules/budget/frontend/pages/budgets/[id].vue
  - backend/app/modules/budget/router.py
last_verified_commit: 4c419ba
---

# Detalle del presupuesto

Vista completa de un presupuesto: cabecera con datos del paciente,
columna principal con las líneas y totales, y columna lateral con
acciones, info y la tarjeta de cobros que aporta el módulo de pagos.
Desde aquí se mueve el presupuesto por todo su flujo
`borrador → enviado → aceptado` y se firma, factura o renegocia.

## De un vistazo

- **Layout en dos columnas.** Izquierda: líneas del presupuesto con
  ítem del catálogo, diente, superficies, cantidad, descuento e IVA.
  Derecha (de arriba abajo): tarjeta de **cobros** (slot
  `budget.detail.sidebar` rellenado por `payments`), **totales**
  (subtotal, descuento, IVA, total), **info** (número, versión,
  validez, creador, plan asociado).
- **Estado del presupuesto** — chip de color en la cabecera. Las
  acciones disponibles dependen del estado.
- **Versionado.** Cada renegociación crea una versión nueva
  enlazada con `parent_budget_id`; el historial se ve desde
  *Historial de versiones*.
- **Firma y PDF.** Un presupuesto aceptado guarda la firma
  (BudgetSignature) y un PDF firmado con su SHA-256 como sello
  anti-manipulación. Hay dos descargas: PDF sin firmar y PDF
  firmado.
- **Crear factura.** Si el presupuesto está *aceptado* y aún tiene
  ítems sin facturar, aparece el botón *Crear factura* que lleva a
  `/invoices/from-budget/{id}`.

## Editar líneas

> Requiere `budget.write` y que el presupuesto esté en `draft`.

1. Pulsa **Editar** sobre la línea o **Añadir ítem** abajo de la
   tabla.
2. Cambia ítem del catálogo, diente, superficies, cantidad,
   descuento o IVA. Los totales se recalculan al guardar.
3. Al guardar se publica un `budget.updated` lógico interno (no
   evento aún), pero el invariante de totales se reescribe en el
   backend.

## Enviar al paciente

> Requiere `budget.write`.

1. Pulsa **Enviar al paciente**. El presupuesto pasa a `sent`,
   se genera un código público y se envía el correo.
2. Se publica `budget.sent` para que módulos de comunicación
   puedan complementar el envío.
3. La barra lateral muestra entonces la tarjeta del
   [enlace público](./p_budget_token.md) con el código de
   verificación.

## Aceptar o rechazar

> Requiere `budget.write` para aceptar online,
> `budget.accept_in_clinic` para aceptación firmada en tablet.

1. **Aceptar (online)** — usado cuando el paciente acepta por el
   enlace público. La aceptación crea una `BudgetSignature` y un
   PDF firmado. Publica `budget.accepted`.
2. **Aceptar en clínica** — botón solo visible con permiso. Abre el
   modal de firma en tablet (firma dibujada). Mismo resultado que
   la aceptación online.
3. **Rechazar** — registra motivo y publica `budget.rejected`.

## Renegociar

> Requiere `budget.renegotiate`.

1. Pulsa **Renegociar**. Crea una nueva versión enlazada con la
   actual; la antigua queda como histórica.
2. Edita ítems y guarda. Publica `budget.renegotiated`.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver detalle, líneas, historial de versiones, descargar PDF | `budget.read` |
| Editar líneas, enviar, aceptar online, rechazar, cancelar, duplicar | `budget.write` |
| Aceptar firmando en clínica | `budget.accept_in_clinic` |
| Renegociar (crear nueva versión) | `budget.renegotiate` |
| Borrar | `budget.admin` |

## Resolución de problemas

- **No veo el botón *Crear factura*.** El presupuesto no está
  aceptado (estado válido: `accepted`), o ya hay una factura no
  cancelada, o todos los ítems se facturaron ya
  (`invoiced_quantity == quantity`).
- **No puedo editar líneas.** El presupuesto ya no está en
  `draft`. Para cambiar precios o cantidades de un presupuesto
  enviado/aceptado debes **renegociar** (requiere
  `budget.renegotiate`).
- **No aparece la tarjeta de cobros.** El módulo `payments` no está
  instalado. La columna lateral muestra solo totales e info.
- **El PDF firmado da 404.** El presupuesto no está aceptado todavía.
  El PDF firmado solo existe a partir del estado `accepted`.
- **Una acción ha fallado.** El aviso de error muestra el motivo que
  devuelve el servidor, no un mensaje genérico. Los habituales son
  *Cannot send empty budget* (añade al menos una línea), *Patient has
  no email address* (rellénalo en la ficha del paciente, o desmarca
  *Enviar por email* y márcalo como entregado en mano) y *Cannot send
  budget from status 'sent'* (ya se había enviado — recarga la
  página).
