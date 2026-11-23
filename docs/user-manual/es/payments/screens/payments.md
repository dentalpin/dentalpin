---
module: payments
screen: list
route: /payments
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
  - backend/app/modules/payments/frontend/pages/payments/index.vue
  - backend/app/modules/payments/router.py
last_verified_commit: 0a9b730
---

# Listado de cobros

Caja operativa de la clínica. Cada fila es un cobro recibido del
paciente, con su importe bruto, las asignaciones a presupuestos o
*a cuenta*, y el importe reembolsado si lo hay. Desde aquí se
registra un cobro nuevo, se reasigna o se emite un reembolso.

## De un vistazo

- **Visión por paciente, no por factura.** Cada cobro pertenece a
  un paciente y se distribuye en *allocations* (presupuesto o
  *on_account*). La factura sale por otro flujo en `billing` y enlaza
  con estos cobros, nunca al revés.
- **Filtros activos en la URL** — método, paciente, rango de fechas,
  *Con reembolsos*, *Con saldo a cuenta*. Compartir el enlace
  comparte los filtros.
- **La búsqueda** encuentra por nombre del paciente o referencia del
  cobro en todos los cobros, no solo en la página visible. Con varios
  métodos marcados se muestran los cobros de cualquiera de ellos; el
  contador y el paginador reflejan el total filtrado.
- **Orden:** por defecto por fecha de cobro descendente. Disponible
  también por importe.
- **Off-books.** El listado nunca cruza *cobrado* contra
  *facturado* — esa comparación es una decisión deliberada del
  producto (ver ADR 0010).
- **Estado de reembolso:** si el cobro tiene reembolsos, ves en rojo
  la cantidad reembolsada bajo el importe. El botón ↺ solo aparece
  cuando queda saldo neto y tu rol puede reembolsar.

## Registrar un cobro

> Requiere `payments.record.write`.

1. Pulsa **Nuevo cobro** en la cabecera (o desde la tarjeta de
   presupuesto en la ficha del paciente).
2. Elige el paciente. Selecciona método y fecha del cobro. Los
   métodos van en dos grupos: **Registrar un cobro ya recibido**
   (efectivo, tarjeta, transferencia, débito, seguro u *otro*) anota
   el dinero tal como entró, y **Cobrar ahora** inicia el cobro por
   una pasarela instalada. El segundo grupo solo aparece si un módulo
   de pasarela ofrece una vía para esta clínica.
3. Elige el **Destino**: un presupuesto abierto del paciente (lista
   con número e importe) o *A cuenta del paciente*. Un cobro *a
   cuenta* queda como saldo del paciente y **no se imputa a ninguna
   factura ni presupuesto** hasta que lo asignes — el formulario lo
   avisa bajo el selector. Para repartir entre varios destinos, abre
   *Opciones avanzadas*; la suma de asignaciones debe igualar el
   importe.
4. **Guardar**. Se publican `payment.recorded` y un
   `payment.allocated` por cada asignación. La tarjeta lateral
   *Cobrado/Pendiente* del presupuesto se actualiza al instante y,
   si el presupuesto tiene facturas emitidas, el cobro se imputa a
   ellas (FIFO) en la misma operación: la factura pasa a
   `partial`/`paid` sin ningún paso extra.

## Reasignar un cobro

> Requiere `payments.record.write`.

1. Abre el cobro pulsando sobre su fila o desde la ficha del paciente.
2. Usa **Reasignar** para mover importe entre presupuestos o entre
   presupuesto y *a cuenta*. Cada cambio publica
   `payment.allocated`; las facturas del presupuesto de origen se
   desvinculan y las del destino se imputan, todo en la misma
   transacción. Desde la ficha del paciente (Administración → Pagos)
   el menú de la fila ofrece **Asignar a presupuesto…** para el caso
   habitual: un anticipo dejado a cuenta que ahora toca aplicar.

## Reembolsar

> Requiere `payments.record.refund`. Por defecto solo admin y
> dentista. Un admin puede otorgarlo a recepción desde *Ajustes →
> Usuarios → Roles*.

1. Pulsa ↺ en la fila del cobro (solo visible si queda saldo neto).
2. Indica el importe (parcial o total) y el motivo. El reembolso
   nunca borra el cobro original: queda como una fila `Refund` y
   resta del *neto* en la cabecera.
3. **Confirmar**. Se publica `payment.refunded` y la fila muestra
   `− 50,00 €` bajo el importe bruto.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver listado, asignaciones, libro mayor del paciente | `payments.record.read` |
| Registrar un cobro y reasignarlo | `payments.record.write` |
| Emitir un reembolso | `payments.record.refund` |
| Acceder a los informes de cobros | `payments.reports.read` |

## Resolución de problemas

- **El listado está vacío con filtros activos.** Pulsa **Limpiar
  filtros** en la barra (chip con el contador). Si sigues sin ver
  cobros, comprueba el rango de fechas — por defecto no hay rango.
- **No me deja guardar el cobro: "suma de asignaciones no coincide".**
  El total de las *allocations* debe igualar el importe bruto. Ajusta
  un valor o añade una asignación *a cuenta* por la diferencia.
- **No veo el botón ↺ aunque mi rol debería poder reembolsar.** El
  cobro ya está reembolsado al 100% (el neto es 0). Solo se permite
  reembolsar mientras quede saldo neto.
- **Una factura no aparece reflejada como saldada en el presupuesto.**
  La factura enlaza con el cobro desde el módulo `billing`. Asegúrate
  de que el cobro está asignado al presupuesto correcto.
