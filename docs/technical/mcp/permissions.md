---
module: mcp
last_verified_commit: d9d8ad97
---

# mcp — permissions

The module contributes **no staff RBAC permissions**
(`get_permissions()` returns `[]`), so there is nothing to namespace.

Access to the endpoint is controlled by the caller's API-token **scope**
(integrations module), not by staff role:

| Scope (token) | Grants |
|---------------|--------|
| `patients:read` | `search_patients`, `get_patient` (read a clinic's patients) |
| `patients:write` | `create_patient` (write a new patient) |

Staff-facing token CRUD lives under the integrations module and is
governed by `integrations.tokens.read` / `integrations.tokens.write`
(see `docs/technical/integrations/permissions.md`).

Because there are no module-level permissions, nothing is added to
`frontend/app/config/permissions.ts` — the MCP surface has no UI.