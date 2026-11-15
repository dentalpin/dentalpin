---
module: payments
screen: payments
route: /reports/payments
related_endpoints:
  - GET /api/v1/payments
  - GET /api/v1/payments/budgets/{budget_id}/allocations
  - GET /api/v1/payments/filters/budgets-by-status
  - GET /api/v1/payments/filters/patients-with-debt
  - GET /api/v1/payments/patients/{patient_id}/ledger
  - GET /api/v1/payments/reports/aging-receivables
  - GET /api/v1/payments/reports/by-method
  - GET /api/v1/payments/reports/by-professional
  - GET /api/v1/payments/reports/refunds
  - GET /api/v1/payments/reports/summary
  - GET /api/v1/payments/reports/trends
  - GET /api/v1/payments/{payment_id}
  - GET /api/v1/payments/{payment_id}/refunds
  - POST /api/v1/payments
  - POST /api/v1/payments/summary/by-budgets
  - POST /api/v1/payments/summary/by-patients
  - POST /api/v1/payments/{payment_id}/reallocate
  - POST /api/v1/payments/{payment_id}/refunds
related_permissions:
  - payments.record.read
  - payments.record.write
  - payments.record.refund
  - payments.reports.read
related_paths:
  - backend/app/modules/payments/frontend/pages/reports/payments/index.vue
last_verified_commit: 71402014
---

# /reports/payments

Cuadro de mando analítico de cobros. La pantalla envuelve los seis
endpoints `/api/v1/payments/reports/*` en una vista calm-design y
permite saltar al detalle del listado `/payments` (o `/patients` para
la antigüedad) desde casi cualquier interacción.

## Permisos

Controlada por `payments.reports.read`. Por defecto la tienen admin,
dentista y recepción. Los drill-downs hacia `/payments` requieren
además `payments.record.read`.

## Estructura

La pantalla se lee de arriba abajo:

1. **Fila hero** — dos tarjetas grandes.
   - *Cobrado neto* muestra el total del periodo, la variación
     porcentual respecto al periodo anterior de igual longitud y una
     línea de tendencia (sparkline) del neto.
   - *Pendiente de cobro* muestra el saldo pendiente de la clínica y
     cuatro mini-barras por bucket de antigüedad (0–30, 31–60, 61–90,
     90+ días). Cada barra es clicable y lleva a `/patients` filtrado
     por deuda.
2. **KPIs secundarios** — cobrado, devuelto, saldo a favor de
   pacientes y tasa de devoluciones. Cobrado y devuelto son clicables;
   "devuelto" añade `has_refunds=true` al filtro.
3. **Evolución del cobro** — gráfico de área del neto por bucket con
   una línea discontinua de devoluciones encima. El selector de
   granularidad (día / semana / mes) está a la derecha del título.
   Hacer clic en un punto abre `/payments` para ese bucket.
4. **Por método** — donut con leyenda. Clic en un sector →
   `/payments?method=…`.
5. **Por profesional** — top 8 de tratamiento ejecutado (no
   cobrado), no de cobros. El clic salta al listado del periodo.
6. **Antigüedad** — barras a ancho completo por bucket. Cada fila
   lleva a `/patients?has_debt=true`.
7. **Devoluciones por motivo** — distribución de devoluciones por
   la causa registrada.

## Filtros

- Periodo: `FilterDateRange` con presets rápidos (Hoy / 7d / 30d /
  Este mes / Trimestre / Año). Por defecto, últimos 90 días.
- Granularidad: solo afecta al gráfico de tendencia.
- En pantallas estrechas, los buckets de antigüedad se muestran en dos
  columnas; en pantallas amplias se muestran cuatro.

## Estados vacíos

Si el periodo seleccionado no tiene datos, las secciones secundarias
se colapsan en una única tarjeta vacía. Cada sección renderiza su
propio empty state cuando solo a ella le faltan datos (sin métodos,
sin profesionales, sin devoluciones, sin pendiente).

## Salvaguarda off-books

Este informe nunca compara cobrado contra facturado ni ejecutado
contra facturado. El desglose por profesional refleja tratamiento
ejecutado, no facturado. Ver `payments/CLAUDE.md` "Gotchas" y ADR
0010.

## Pantallas relacionadas

- `/payments` — listado de cobros, destino de la mayoría de
  drill-downs.
- `/patients` con `has_debt=true` — destino de los drill-downs de
  antigüedad.

