---
module: treasury
screen: treasury
route: /treasury
last_verified_commit: 695eb0f9
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
nunca almacenado).

## Qué puedes hacer

- **Crear** cuentas de efectivo o banco (nombres únicos por clínica).
- **Transferir** entre cuentas — ambas patas comparten una operación
  y aparecen en ambos movimientos.
- **Corregir** una cuenta con concepto obligatorio (auditoría, nunca
  ediciones silenciosas).
