---
module: billing
screen: create
route: /invoices/new
related_endpoints:
  - GET /api/v1/billing/series
  - GET /api/v1/billing/settings
  - POST /api/v1/billing/invoices
  - POST /api/v1/billing/invoices/{invoice_id}/items
related_permissions:
  - billing.read
  - billing.write
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/new.vue
  - backend/app/modules/billing/router.py
last_verified_commit: eab5bb31
---

# Nueva factura

Formulario para crear una factura **libre** (sin presupuesto). Al
guardar nace como borrador (`draft`) y se abre el
[detalle](./invoices_id.md) para emitirla cuando proceda.

Para facturar a partir de un presupuesto aceptado usa la
[pantalla específica](./invoices_from-budget_budgetId.md) — copia
ítems con sus snapshots de precio e IVA, evita errores de captura.

## De un vistazo

- **Receptor.** El paciente. Los datos de facturación (nombre, NIF,
  dirección, email) no se teclean aquí: el borrador los lee en vivo
  de la ficha del paciente y se congelan al emitir. Una etiqueta
  indica si al paciente le faltan datos de facturación, con enlace
  para completarlos en su ficha.
- **Líneas libres.** Añade ítems del catálogo con cantidad,
  descuento, IVA. También puedes meter líneas manuales (sin ítem
  del catálogo) cuando lo necesites para cargos especiales.
- **No emite todavía.** Crear no emite la factura: solo guarda el
  borrador. La emisión vive en el detalle.
- **Numeración.** No se asigna en este paso; el número fiscal solo
  llega al **emitir** (botón en el detalle), que toma el siguiente
  de la serie activa.
- **Plazo de pago.** Precargado con el valor por defecto de la
  clínica de las [preferencias de facturación](./settings_preferences.md)
  (`default_payment_term_days`); cámbialo por factura si lo
  necesitas.

## Crear una factura libre

> Requiere `billing.write`.

1. Selecciona paciente. Si la etiqueta indica que faltan datos de
   facturación, complétalos en la ficha del paciente (enlace bajo el
   selector).
2. Añade líneas: ítem del catálogo, cantidad, descuento, IVA.
3. Revisa totales (subtotal, descuento, IVA, total).
4. **Guardar**. La factura nace en `draft`. Para emitirla, abre el
   [detalle](./invoices_id.md) y pulsa **Emitir**.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Acceder al formulario | `billing.read` |
| Crear borrador | `billing.write` |

## Resolución de problemas

- **Aviso "Sin serie activa".** Falta marcar una serie como activa
  para el ejercicio en *Ajustes → Series de facturación*. Puedes
  guardar el borrador sin serie, pero no podrás emitirlo.
- **No encuentro un ítem del catálogo.** Comprueba que esté activo
  y que tu rol tenga `catalog.read`. Si necesitas un cargo
  específico, mete una línea libre.
- **No me sale el botón *Pagador distinto*.** Está disponible en
  cualquier borrador (no requiere permiso extra). Si no se ve,
  refresca; puede ser un fallo de carga del catálogo o de la
  configuración de la clínica.
