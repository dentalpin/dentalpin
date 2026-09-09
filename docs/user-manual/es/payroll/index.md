---
module: payroll
---

# Nómina

Nómina del personal, solo para administradores (rol admin). Cuatro
páginas en las entradas de nómina:

- **[Perfiles](./screens/profiles.md)** — un perfil por empleado
  (base, moneda, cuenta, NIF). Los secretos siempre se muestran
  enmascarados — solo los últimos 4 dígitos. Para cambiarlos,
  introduce el valor completo; si lo omites se conserva. Desactiva en
  lugar de eliminar.
- **[Periodos](./screens/periods.md)** — un periodo `AAAA-MM` cada
  vez; muévelo de borrador a cerrado a pagado con confirmación. Los
  cerrados bloquean sus apuntes.
- **[Detalle del período](./screens/period-detail.md)** — apuntes por
  empleado (bruto, deducciones y neto tal cual; el neto debe ser bruto
  menos deducciones, validado en el formulario y la API).
- **[Informes](./screens/reports.md)** — agregado mensual por periodo
  y anual por año, en la moneda de la clínica. Sin cálculo de
  impuestos en v1.
