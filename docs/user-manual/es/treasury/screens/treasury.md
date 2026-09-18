---
module: treasury
screen: treasury
route: /treasury
last_verified_commit: 7f721882604ba9c8ae4f21229f816787e46bf7bc
related_endpoints:
  - GET /api/v1/treasury/accounts
  - POST /api/v1/treasury/accounts
  - PATCH /api/v1/treasury/accounts/{account_id}
  - DELETE /api/v1/treasury/accounts/{account_id}
  - GET /api/v1/treasury/accounts/{account_id}/entries
  - POST /api/v1/treasury/transfers
  - POST /api/v1/treasury/accounts/{account_id}/corrections
related_permissions:
  - treasury.read
  - treasury.write
related_paths:
  - backend/app/modules/treasury/frontend/pages/treasury/index.vue
---

# Tesorería

En la entrada **Tesorería** de la barra lateral (solo admin). Cada
cuenta muestra su saldo derivado (apertura + movimientos con signo,
nunca almacenado), con formato en la moneda de la clínica. Las
operaciones fallidas muestran su error en lugar de cerrar el modal
en silencio.

## Qué puedes hacer

- **Crear** cuentas de efectivo o banco (nombres únicos por clínica).
- **Transferir** entre cuentas — ambas patas comparten una operación
  y aparecen en ambos movimientos.
- **Corregir** una cuenta con concepto obligatorio (auditoría, nunca
  ediciones silenciosas).
- El extracto muestra fecha e importe con signo en las salidas; los
  saldos negativos se ven en rojo (aviso, nunca bloqueo). Los
  importes aceptan coma decimal (`25,50`) y los desplegables de
  traspaso solo listan cuentas activas.
