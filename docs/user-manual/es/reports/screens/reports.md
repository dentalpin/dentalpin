---
module: reports
screen: dashboard
route: /reports
related_endpoints:
  - GET /api/v1/reports/scheduling/first-visits
  - GET /api/v1/reports/scheduling/funnel
related_permissions:
  - reports.billing.read
  - reports.budgets.read
  - reports.scheduling.read
related_paths:
  - backend/app/modules/reports/frontend/pages/reports/index.vue
  - backend/app/modules/reports/frontend/composables/useDashboardSnapshot.ts
  - backend/app/modules/reports/frontend/components/dashboard/
last_verified_commit: 2195ad0e
---

# Dashboard de la clínica

Punto de entrada al área de informes. Vista ejecutiva con los
indicadores clave para dueño o gerente, todos filtrables por rango de
fecha — salvo las métricas marcadas como *foto del momento*.

## De un vistazo

- **Fila hero (4 tarjetas).** Caja cobrada, saldo a favor de
  pacientes, producción total y desglose por forma de pago.
- **Fila de gráficos.** Cobros en el periodo (con devoluciones
  superpuestas) y producción por doctor.
- **Fila operativa.** Pacientes nuevos, tasa de no-show y
  ticket medio cobrado.
- **Atención.** Cuentas por cobrar agrupadas por antigüedad (0-30 /
  31-60 / 61-90 / 90+).
- **Drilldown.** Tarjetas que enlazan al detalle de facturación,
  presupuestos y agenda — preserva el flujo previo de navegación.

## Filtro de rango

- Único filtro `Periodo` en la cabecera, *sticky* en scroll.
- Por defecto, el rango es el mes en curso.
- Presets disponibles: hoy, últimos 7, últimos 30, este mes, este
  trimestre, este año.
- El rango se persiste en la URL (`?from=…&to=…`) para que un
  responsable pueda marcar un periodo como favorito.

## Métricas *foto del momento*

Dos tarjetas no cambian con el rango: muestran el estado actual de
la clínica.

- **Saldo a favor del paciente** — dinero adelantado por pacientes
  que aún no se ha aplicado a presupuestos o facturas.
- **Cuentas por cobrar** — distribución por antigüedad de la deuda
  pendiente.

Ambas llevan el badge `Hoy` para evitar lecturas erróneas.

## Permisos

| Lo que ves | Permiso requerido |
|------------|-------------------|
| Caja cobrada, saldo a favor, producción, formas de pago, gráficos, ticket medio cobrado, cuentas por cobrar | `payments.reports.read` (detalle: la pantalla de informes de pagos) |
| Pacientes nuevos, tasa de no-show | `reports.scheduling.read` |
| Drilldown a Facturación | `reports.billing.read` |
| Drilldown a Presupuestos | `reports.budgets.read` |
| Drilldown a Agenda | `reports.scheduling.read` |

Si el rol no tiene un permiso, la tarjeta no aparece y el grid se
recompone sin huecos.

## Resolución de problemas

- **No veo ninguna métrica.** Tu rol no tiene ninguno de los
  permisos requeridos. Pide a un admin desde *Ajustes → Usuarios →
  Roles*.
- **Las tarjetas de pagos están vacías.** No hay cobros registrados
  en el rango. Comprueba que el módulo de cobros esté en uso o
  amplía el periodo.
- **Producción a cero.** La producción se nutre de los tratamientos
  finalizados (sesiones completadas o entradas del odontograma). Si
  el equipo no marca el tratamiento como hecho, no aparece.
- **Cifras no cuadran con la página de detalle.** El detalle de
  facturación trabaja sobre facturas; el dashboard trabaja sobre
  cobros. Son ejes distintos a propósito — la clínica puede dejar
  fuera de factura cierto trabajo, así que comparar pagado con
  facturado no aporta señal real.
