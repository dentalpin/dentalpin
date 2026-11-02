---
module: billing
screen: detail
route: /invoices/[id]
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
  - backend/app/modules/billing/frontend/pages/invoices/[id]/index.vue
  - backend/app/modules/billing/router.py
last_verified_commit: edc08ff
---

# Detalle de factura

Vista de una factura concreta. Cabecera con datos legales (emisor,
receptor, NIF, dirección), líneas, totales y panel lateral con
cobros enlazados, historial y estado de envío fiscal (verifactu).
Desde aquí se emite, se manda al paciente y, si procede, se anula o
se emite un abono.

## De un vistazo

- **Presupuesto y plan vinculados.** Una factura creada desde un presupuesto enlaza a él y, si ese presupuesto nació de un plan de tratamiento, también al plan.
- **Datos legales** — receptor (paciente o tercero pagador), NIF,
  dirección fiscal y serie + número (en `issued`). Si el pagador no
  es el paciente se ve un chip *Pagador distinto*.
- **Cobros enlazados.** Listado de `invoice_payments` con importe y
  método, y el botón **Cobrar** (facturas `issued`/`partial`). El
  cobro se registra en el módulo `payments` y se enlaza aquí en la
  misma operación. Si la factura nació de un presupuesto, el cobro
  se asigna a ese presupuesto: la tarjeta *Cobrado* del presupuesto
  y la ficha del paciente lo reflejan al instante. Al revés también:
  cobrar desde el presupuesto imputa a sus facturas emitidas, y al
  emitir una factura desde un presupuesto ya cobrado (anticipo) la
  factura nace `paid`.
- **PDF.** Dos formatos: borrador (vista previa con marca de agua)
  y definitivo (solo desde `issued`). El PDF se genera con
  WeasyPrint. Si una línea usa un tipo de IVA con nota legal (p. ej.
  la exención española, art. 20.Uno.5º LIVA, sembrada por el preset
  `es`), la nota se imprime en el bloque de avisos legales. El pie
  muestra fecha y hora de generación en la zona horaria de la
  clínica.
- **Historial.** Cambios de estado y eventos clave en orden
  cronológico.
- **VeriFactu.** Si el módulo está instalado, al emitir se encola el
  envío a AEAT. El estado (`pending`, `sent`, `rejected`) se ve en
  el lateral.

## Emitir una factura

> Requiere `billing.write`.

1. Comprueba que los datos legales y las líneas son correctos. Una
   vez emitida, no se podrá editar. Si el paciente no tiene NIF (ni
   DNI/NIE), el borrador muestra *Faltan datos* y el botón principal
   pasa a ser **Completar datos**: abre el modal de facturación del
   paciente y vuelve a la factura al guardar.
2. Pulsa **Emitir**. La serie activa asigna número fiscal, se
   publica `invoice.issued` y se congela el documento.
3. Si `verifactu` está instalado, el *hook* encolará el envío a
   AEAT y verás el estado en el panel lateral.

## Enviar por email

> Requiere `billing.write`.

1. Pulsa **Enviar por email**. Se manda al correo de contacto del
   receptor con el PDF adjunto.
2. Publica `invoice.sent`. El historial registra el envío.

## Anular o emitir abono

> Requiere `billing.admin` para anular, `billing.write` para emitir
> abono.

- **Anular** — marca la factura como `void`. Su número queda en el
  histórico para auditoría. Solo admin.
- **Crear nota de crédito** — emite un abono asociado con los
  importes de la factura origen. Pasa por el mismo flujo de emisión.
  El conjunto de abonos de una factura, borradores incluidos, no puede
  superar su total; una vez abonada por completo, uno nuevo se rechaza
  indicando el importe que queda por abonar. Borra un abono en borrador
  para liberar su importe.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver factura, PDF e historial | `billing.read` |
| Editar borrador, emitir, enviar email, crear abonos | `billing.write` |
| Anular factura emitida | `billing.admin` |

## Resolución de problemas

- **No puedo editar líneas.** La factura ya no está en `draft`.
  Anula y emite una nueva, o emite un abono parcial.
- **El PDF descargado es la vista previa con marca de agua.** La
  factura está en `draft` o `void`. El PDF definitivo solo existe
  para facturas emitidas.
- **VeriFactu en `rejected`.** Mira el panel lateral o el módulo
  `verifactu` para el motivo. Suele requerir editar datos del
  emisor o del receptor y reenviar manualmente.
- **Cobré desde la ficha del paciente y la factura sigue sin cobrar.**
  El cobro quedó *a cuenta* (sin presupuesto). En Administración →
  Pagos usa **Asignar a presupuesto…** sobre ese cobro; si la factura
  viene de ese presupuesto, se imputa sola.
