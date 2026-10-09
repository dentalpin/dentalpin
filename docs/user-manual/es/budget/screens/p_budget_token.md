---
module: budget
screen: public
route: /p/budget/[token]
related_endpoints:
  - GET /api/v1/budget/public/budgets/{token}
  - GET /api/v1/budget/public/budgets/{token}/meta
  - GET /api/v1/budget/public/budgets/{token}/pdf/signed
  - POST /api/v1/budget/public/budgets/{token}/accept
  - POST /api/v1/budget/public/budgets/{token}/reject
  - POST /api/v1/budget/public/budgets/{token}/verify
related_permissions:
related_paths:
  - backend/app/modules/budget/frontend/pages/p/budget/[token].vue
  - backend/app/modules/budget/router.py
last_verified_commit: a13bd29
---

# Aceptación pública del paciente

Vista pública del presupuesto que el paciente abre desde el enlace
que recibe por correo o WhatsApp. **No requiere sesión** de la app;
se autentica por token + un segundo factor (código numérico) según
[ADR 0006](../../../../adr/0006-budget-public-link-2-factor-auth.md).
Desde aquí el paciente puede ver el detalle, descargar el PDF y
aceptar o rechazar el presupuesto.

Esta pantalla es para el **paciente**, no para el personal de la
clínica. La describimos aquí para que recepción sepa qué ve el
paciente cuando le pasan el enlace.

## De un vistazo

- **Los precios son netos.** Cada tratamiento muestra el precio con descuento (de línea + global); si hay descuento, el precio original aparece tachado al lado, de modo que el paciente ve de qué se compone el total del pie.
- **Doble factor.** Para abrir el contenido el paciente teclea el
  código numérico que la clínica le ha facilitado (lo configuras
  desde el detalle del presupuesto, *Definir código público*). El
  endpoint `POST /verify` impone un *rate-limit* y, al acertar,
  guarda una cookie HttpOnly de sesión limitada al path
  `/api/v1/budget/public/budgets/{token}`. La cookie no sirve para abrir
  otro presupuesto distinto.
- **Idempotente al primer visto.** La primera vez que el paciente
  abre la vista (tras verificar) publicamos `budget.viewed` con un
  timestamp. Reabrir no genera más eventos.
- **Acciones del paciente.** *Aceptar* y *Rechazar* son acciones
  públicas: dejan la firma asociada y publican
  `budget.accepted` / `budget.rejected`. Aceptar genera el PDF
  firmado y guarda su SHA-256 como huella anti-manipulación.
- **PDF firmado.** Tras aceptar, el botón *Descargar PDF firmado*
  llama a `GET /pdf/signed` con la cookie. Está limitado a 10
  descargas/minuto por token; cada acceso queda registrado en
  `BudgetAccessLog`.

## Lo que ve el paciente

1. Pantalla de bienvenida con el nombre de la clínica y un campo de
   código.
2. Tras verificar: cabecera con clínica + paciente, listado de
   ítems con totales, validez y profesional asignado.
3. Botones **Aceptar** y **Rechazar** (este último pide motivo).
4. **Descargar PDF** del presupuesto.

## Cómo ayudar a un paciente con problemas

> Acciones del lado clínica.

- **Reenviar enlace** desde el detalle: *Reenviar*. Publica
  `budget.reminder_sent`.
- **Cambiar / generar nuevo código público** desde *Definir código
  público*.
- **Desbloquear si pasó el límite de intentos** — endpoint
  `POST /unlock-public` (botón en el detalle cuando hay bloqueo
  vigente).

## Permisos

Pantalla pública: no hay permisos de DentalPin asociados. Las
acciones internas que la soportan sí requieren `budget.write` en la
clínica (enviar, reenviar, generar/cambiar código, desbloquear).

## Resolución de problemas

- **"Código incorrecto" repetido.** El paciente teclea mal el
  código; tras varios intentos se bloquea el enlace temporalmente.
  Desbloquéalo desde el detalle.
- **El paciente acepta pero no ve el PDF firmado.** El PDF firmado
  se genera al aceptar; pídele recargar tras unos segundos. Si
  persiste, comprueba en `BudgetAccessLog` si hay errores.
- **La sesión caduca.** La cookie es por token y de duración
  corta. Si el paciente cierra el navegador, tendrá que volver a
  meter el código.
