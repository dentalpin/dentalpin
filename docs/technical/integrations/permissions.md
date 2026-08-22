---
module: integrations
last_verified_commit: d426572
---

# Integrations — permissions

Returned by `IntegrationsModule.get_permissions()`
(relative names; the registry namespaces them as `integrations.<name>`).
Admin-only in Phase 1 — every other role gets `[]` in
`manifest.role_permissions`.

| Permission | Allows | Required by |
|------------|--------|-------------|
| `integrations.subscriptions.read` | List a clinic's webhook subscriptions | `GET /api/v1/integrations/webhooks/subscriptions` |
| `integrations.subscriptions.write` | Create, update, or delete a webhook subscription | `POST`/`PATCH`/`DELETE /api/v1/integrations/webhooks/subscriptions[/{id}]` |
| `integrations.tokens.read` | List a clinic's API tokens | `GET /api/v1/integrations/tokens` |
| `integrations.tokens.write` | Create or revoke an API token | `POST /api/v1/integrations/tokens`, `POST /api/v1/integrations/tokens/{id}/revoke` |

## Role assignment

See `backend/app/core/auth/permissions.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/integrations/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
