# treasury — permissions

| Permission | Grants | Gated endpoints |
|---|---|---|
| `treasury.read` | list accounts + balances, statements, page | `GET /accounts`, `GET /accounts/{id}/entries` |
| `treasury.write` | create/rename/delete, transfers, corrections | `POST/PATCH/DELETE /accounts*`, `POST /transfers` |

Role defaults: admin `*` only (payroll-grade blast radius until a
clinic widens grants via the roles UI).
