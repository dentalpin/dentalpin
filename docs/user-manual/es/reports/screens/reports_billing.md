---
module: reports
screen: billing
route: /reports/billing
related_endpoints:
  - GET /api/v1/reports/billing/aging
  - GET /api/v1/reports/billing/by-payment-method
  - GET /api/v1/reports/billing/by-professional
  - GET /api/v1/reports/billing/gaps
  - GET /api/v1/reports/billing/issued-trend
  - GET /api/v1/reports/billing/overdue
  - GET /api/v1/reports/billing/summary
  - GET /api/v1/reports/billing/vat-summary
related_permissions:
  - reports.billing.read
  - reports.financial.read
related_paths:
  - backend/app/modules/reports/frontend/pages/reports/billing.vue
  - backend/app/modules/reports/router.py
last_verified_commit: b1b82f5
---

# Informes de facturación

Cuadro de mando de facturación. Resume lo emitido y lo pendiente,
con desglose por profesional, método de pago, IVA, vencimientos y
huecos de facturación. Sirve para cierre mensual, conciliación y
preparación de IVA.

## De un vistazo

- **Rango por defecto** — últimos 90 días. El filtro de fechas vive
  en la cabecera y se aplica a todas las secciones excepto a las que
  son *ahora* (vencimientos, huecos).
- **Resumen** — totales facturados, número de facturas y media por
  factura para el rango.
- **Por método de pago** — desglose de lo que se ha facturado a cada
  método. **Ojo:** lo cobrado por método vive en
  [informes de cobros](../../payments/screens/reports_payments.md);
  aquí ves *qué se ha facturado*.
- **Por profesional** — facturación atribuida a cada profesional.
- **IVA** — agregado por tipo de IVA. Útil para preparar el modelo
  fiscal del periodo.
- **Vencidos y huecos** — facturas pasadas de fecha y series con
  saltos en la numeración (gaps), si los hay.
- **Antigüedad** — totales pendientes por tramo
  (0–30/31–60/61–90/90+ días, solo importes emitidos). Los mismos
  números que la tarjeta del panel; añade `?format=csv` al endpoint
  para la hoja de cálculo.
- **Tendencia emitida** — totales emitidos por mes del rango
  (`?format=csv` disponible).

## Drill-downs

- Cualquier sección que represente facturas individuales (vencidas,
  huecos) tiene un *Abrir en /invoices* que lleva al listado
  filtrado.
- Para auditar un profesional o un método concreto, usa los filtros
  del listado de facturas con el mismo rango.

## Salvaguarda *off-books*

Este informe **no** cruza *cobrado* contra *facturado*: la
comparación se evita por diseño (ADR 0010). Si necesitas saber qué
queda por cobrar, ve a
[/reports/payments](../../payments/screens/reports_payments.md), que
no compara contra `invoiced`.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver cualquiera de las secciones | `reports.billing.read` |
| Acceder al listado base de facturas (drill-down) | `billing.read` |

## Resolución de problemas

- **Una sección está vacía.** El rango por defecto no captura datos
  o el filtro elimina todo. Amplía el rango.
- **Los huecos en la serie son raros.** Si solo emites borradores no
  consumes número; un hueco real solo aparece al borrar una factura
  emitida (no permitido) o al usar series con resets antiguos.
  Investiga en el listado.
- **El IVA no cuadra con tu modelo.** Comprueba que las facturas en
  el rango están emitidas (no borradores) y que los tipos de IVA del
  catálogo están bien definidos en *Ajustes → Tipos de IVA*.
