---
module: billing
last_verified_commit: b1b82f5
---

# Facturación

El módulo de facturación gestiona las facturas, abonos y notas de
crédito de la clínica, su PDF y el cumplimiento fiscal (la
integración con AEAT vive en el módulo opcional `verifactu`). Lleva
también la configuración de series de facturación.

Las facturas pueden crearse desde cero o desde un presupuesto
aceptado del módulo `budget`. Los **cobros** se enlazan con las
facturas a través de `invoice_payments`, pero los cobros viven en el
módulo `payments` (`billing` depende de `payments`, no al revés).

## Pantallas

- [Listado de facturas](./screens/invoices.md) — buscar, filtrar y
  abrir facturas.
- [Detalle de factura](./screens/invoices_id.md) — ver la factura,
  PDF, cobros enlazados, emitir, enviar y anular.
- [Editar borrador](./screens/invoices_id_edit.md) — solo facturas
  en estado `draft`.
- [Nueva factura](./screens/invoices_new.md) — crear factura libre
  (sin presupuesto).
- [Factura desde presupuesto](./screens/invoices_from-budget_budgetId.md)
  — facturar todos o parte de los ítems de un presupuesto aceptado.
- [Series de facturación (ajustes)](./screens/settings_invoice-series.md)
  — gestionar prefijos, contadores y series activas.
- [Preferencias de facturación (ajustes)](./screens/settings_preferences.md)
  — plazo de pago, pie de factura y datos bancarios.

## Referencia rápida

| Acción | Permiso requerido |
|--------|-------------------|
| Ver facturas, descargar PDF | `billing.read` |
| Crear borradores, editar, emitir, enviar email | `billing.write` |
| Anular o eliminar serie | `billing.admin` |
| Editar series de facturación | `billing.admin` |

## Módulos relacionados

- **Presupuestos (`budget`)** — fuente principal de líneas: una
  factura puede generarse a partir de un presupuesto aceptado.
- **Cobros (`payments`)** — `billing` depende de `payments`; una
  factura enlaza con uno o varios cobros vía `invoice_payments`.
- **Catálogo** — proveedor de ítems facturables y tipos de IVA.
- **VeriFactu** — módulo de compliance fiscal (AEAT). Engancha por
  *hook* al evento `invoice.issued` para encolar el envío.
- **Informes** — los KPIs y la tendencia de facturación viven en
  `/reports/billing`.
