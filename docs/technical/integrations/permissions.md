---
module: integrations
last_verified_commit: ab94969a
---

# Integrations — permissions

Returned by `IntegrationsModule.get_permissions()`
(relative names; the registry namespaces them as `integrations.<name>`).
Admin-only — every other role gets `[]` in `manifest.role_permissions`.

The public data-read API (`/api/v1/integrations/public/...`) is NOT gated
by RBAC permissions — it uses API-token scopes (`patients:read`) instead
of staff JWT claims. The MCP module also consumes integration token
scopes (`patients:read`, `patients:write`) but does so through its own
auth middleware, not the public REST endpoints.

| Permission | Allows | Required by |
|------------|--------|-------------|
| `integrations.subscriptions.read` | List a clinic's webhook subscriptions | `GET /api/v1/integrations/webhooks/subscriptions` |
| `integrations.subscriptions.write` | Create, update, or delete a webhook subscription | `POST`/`PATCH`/`DELETE /api/v1/integrations/webhooks/subscriptions[/{id}]` |
| `integrations.tokens.read` | List a clinic's API tokens | `GET /api/v1/integrations/tokens` |
| `integrations.tokens.write` | Create or revoke an API token | `POST /api/v1/integrations/tokens`, `POST /api/v1/integrations/tokens/{id}/revoke` |

## API-token scopes (public data-read API)

Validated against `SUPPORTED_TOKEN_SCOPES` in `triggers.py` at token
creation time. Enforced per-endpoint by the `require_scope()` dependency in
`public.py`.

| Scope | Allows | Required by |
|-------|--------|-------------|
| `patients:read` | Read patients for the token's clinic (incl. the structured `phone`/`email`/`national_id` find params) | `GET /api/v1/integrations/public/patients`, `GET /api/v1/integrations/public/patients/{id}` |
| `patients:write` | Create a new patient for the token's clinic | MCP `tools/call` → `patients.create_patient` (no public REST endpoint; see `docs/technical/mcp/overview.md`) |

`GET /api/v1/integrations/public/ping` (token introspection — the auth
test a Zapier/Make app runs) requires a valid token but no scope.
Every authenticated public request stamps the token's `last_used_at`.

## Role assignment

See `backend/app/core/auth/permissions.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/integrations/__init__.py`.
2. Grant it to roles in `manifest.role_permissions`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.

## Adding a new token scope

1. Add the scope string to `SUPPORTED_TOKEN_SCOPES` in `triggers.py`.
2. Add a consumer endpoint to `public.py` with `Depends(require_scope(...))`, or register the scope in the MCP module's `server.py` `_SCOPE_TO_PERMISSION` map if the consumer is MCP, not the REST API.
3. Add a row to the token scopes table above.
