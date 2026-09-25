---
module: razorpay
last_verified_commit: 8fb8f8cb
---

# Razorpay

Página de inicio del módulo `razorpay` en el manual de usuario. Este
módulo permite a una clínica en India cobrar pagos de pacientes de
forma electrónica a través de Razorpay — UPI, un código QR escaneable,
tarjetas y enlaces de pago — directamente desde el listado
`/payments` y la pestaña de pagos del paciente. Un pago solo aparece
como cobrado cuando el propio Razorpay lo confirma; nada de esto
cambia cómo funciona un pago registrado manualmente (efectivo,
datáfono, transferencia).

## Pantallas

- `/settings/razorpay` — configura la conexión de la clínica con
  Razorpay. Ver
  [screens/settings-razorpay.md](./screens/settings-razorpay.md).

El panel de cobro y el detalle de la transacción viven dentro de
`/payments` (y la pestaña Pagos del paciente) en lugar de tener su
propia ruta — consulta el manual del módulo de pagos para esa
pantalla, y [Pantallas relacionadas](#pantallas-relacionadas) para lo
que este módulo añade a esa vista.

## Permisos

- `razorpay.settings.read` / `.write` — conectar/gestionar la
  pasarela (solo administradores por defecto).
- Cobrar un pago o emitir un reembolso a través de Razorpay usa los
  mismos permisos `payments.record.write` / `payments.record.refund`
  que registrar un pago manualmente — no se necesita ningún permiso
  adicional.

## Pantallas relacionadas

- `/payments` — pulsa **Nuevo pago** como siempre. Para clínicas en
  India con una configuración de Razorpay activa, la fila de métodos
  dentro de ese mismo modal ofrece tres chips adicionales junto a
  efectivo/tarjeta/transferencia/etc.: **UPI QR**, **Razorpay** (pago
  con tarjeta) y **Enlace de pago**. No existe un botón de Razorpay
  aparte junto a "Nuevo pago" — al elegir uno de los tres chips, el
  modal cambia al panel de cobro (código QR / Checkout.js / enlace
  copiable), que consulta el estado hasta que Razorpay confirma el pago
  y solo entonces cierra el modal. Los pagos cobrados mediante la
  pasarela muestran una pequeña insignia tipo "Razorpay · UPI" bajo la
  línea de fecha/método de la fila, que abre el detalle de la
  transacción (registro de auditoría, asignación e historial de
  reembolsos).
- Ficha del paciente → pestaña Pagos — los mismos tres chips aparecen
  dentro del modal "Cobrar" de esa pestaña, junto a los métodos
  manuales.

## Referencias técnicas

- [Resumen técnico](../../../technical/razorpay/overview.md)
- [Permisos](../../../technical/razorpay/permissions.md)
- [Eventos](../../../technical/razorpay/events.md)
- [Resumen de payment_gateways](../../../technical/payment_gateways/overview.md) — el módulo neutral al proveedor en el que se conecta este
- [ADR 0029 — arquitectura de adaptadores de pasarela de pago](../../../adr/0029-payment-gateway-adapter-architecture.md)
