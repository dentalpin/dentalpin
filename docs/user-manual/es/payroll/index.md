---
module: payroll
---

# Nómina

Nómina del personal, solo para administradores. Los perfiles guardan
condiciones salariales con banco/impuestos cifrados; los periodos
mensuales recogen apuntes; los informes los agregan. Sin cálculo de
impuestos en v1.

## Flujos

- **Perfiles**: un perfil por empleado (base, moneda, cuenta, NIF).
  Los secretos siempre se muestran enmascarados — solo los últimos 4
  dígitos. Para cambiarlos, introduce el valor completo; si lo omites
  se conserva. Desactiva en lugar de eliminar.
- **Periodos**: un periodo `AAAA-MM` cada vez; muévelo de borrador a
  cerrado a pagado. Los cerrados bloquean sus apuntes.
- **Apuntes**: bruto, deducciones y neto por empleado (el neto debe
  ser bruto menos deducciones). Uno por empleado y periodo.
- **Informes**: agregado mensual por periodo y anual por año, en la
  moneda de la clínica.
