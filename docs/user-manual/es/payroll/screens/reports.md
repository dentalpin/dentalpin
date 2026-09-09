---
module: payroll
screen: reports
route: /payroll/reports
last_verified_commit: 0b59a2a2
related_endpoints:
  - GET /api/v1/payroll/reports/monthly?month=
  - GET /api/v1/payroll/reports/annual?year=
related_permissions:
  - payroll.reports.read
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/reports/index.vue
---

# Informes

En la entrada **Informes** de la nómina (solo admin). Dos tarjetas:
total mensual para un mes `AAAA-MM` y total anual para un año, ambos
en la moneda de la clínica.

## Qué puedes hacer

- **Mensual**: escribe el mes y carga número de movimientos, bruto
  total, deducciones totales y neto total.
- **Anual**: escribe el año (por defecto el actual) y carga número de
  períodos con los mismos totales del año.
