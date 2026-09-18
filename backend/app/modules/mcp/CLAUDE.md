# MCP module

Model Context Protocol bridge: exposes a curated, scope-gated slice of
DentalPin's agent tools to external AI clients (Claude Desktop, Cursor,
any MCP-compatible host) over the streamable-HTTP transport.

## Public API

Endpoint at `/api/v1/mcp/` ([SDK](https://www.npmjs.com/package/@modelcontextprotocol/sdk)
`streamable-http` transport; the bare `/api/v1/mcp` 307-redirects there).

Auth is `Authorization: Bearer dp_...` — the **same API tokens the
integrations module issues** (`integrations.tokens.*`). No JWT, no
browser session. Access is gated on the token carrying at least one
MCP scope (`auth.py`, `MCP_SCOPES`): `patients:read` grants the read
tools, `patients:write` adds `create_patient`.

## Dependencies

`manifest.depends = ["patients", "integrations"]`. Reads
`IntegrationsService.authenticate_token` (integrations) and registry
tools owned by patients.

## Permissions

**None.** Staff RBAC (`get_permissions()` → `[]`) doesn't govern this
endpoint — machine access is scoped by API-token scope, not staff role.

## Tools exposed

None of its own (`get_tools()` → `[]`). Instead `server.py` re-exposes
a closed allowlist of OTHER modules' registry tools, namespaced by
qualified key:

| Tool | Curated key | Category |
|---|---|---|
| `search_patients` | `patients.search_patients` | READ |
| `get_patient` | `patients.get_patient` | READ |
| `create_patient` | `patients.create_patient` | WRITE |

Every `tools/call` flows through `tool_registry.call` — guardrails,
RBAC (enforced against the RBAC grants the token's scopes translate to:
`patients:read` → `patients.read`, `patients:write` → `patients.write`),
input validation and the audit log (keyed on deterministic per-token
agent/session ids) all still run at the single chokepoint. A session
only *lists* tools its scopes could call. `update_patient` stays out —
there's no shape for safely patching via autonomous machine clients yet.

## Events emitted

None.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- **Transport only**: no models, no DB tables, so uninstall is a no-op
  beyond unmounting the router. Ships a single no-op Alembic revision
  (`mcp_0001`, own branch, empty upgrade/downgrade) purely so
  `removable=True` has an isolated branch to validate against and
  `ModuleService.uninstall` has a `base_revision` to allow — same
  pattern as `recall_reminders` (see its `rr_0001_noop` migration).

## Gotchas / non-obvious invariants

- **The session manager is process-single-use.** `build_mcp_router()`
  wraps `StreamableHTTPSessionManager.run()` in a lazy task
  (`router._LazyManagedMCPApp`) started on first request; `run()` can
  only be entered once per manager, so each router instance is one-shot
  for the process lifetime. In tests, one test function per process
  exercises the endpoint (fresh loop + fresh manager otherwise).
- **Auth happens before the manager runs.** The middleware lives
  *outside* the lazy runner, so unauthenticated traffic never touches
  the session group.
- **Auth is shared with the integrations public API.** The middleware
  calls `IntegrationsService.authenticate_token`, so the per-token
  fixed-window rate limit (60/min + 1000/day) applies to every MCP
  request — `initialize`, `tools/list`, bad-token floods alike — and
  each successful auth stamps the token's `last_used_at` (visible on
  the admin token list). A rate-limited token gets a 429
  `rate_limited` JSON response, distinct from the 401 gate.
- **Audit rows require real `agents`/`agent_sessions` rows.** Their ids
  are deterministic UUIDs derived from the API token
  (`server._ensure_agent_and_session`, UPSERT). Every call from one
  token groups under one agent/session.
- **Bare path redirects.** App-wide `redirect_slashes=False`; the bare
  `/api/v1/mcp` responds 307 → `/api/v1/mcp/`, which MCP SDK clients
  follow while preserving method and body. Configure the client with
  either; both work.
- **`json_response=True`** on the manager: responses are `application/
  json`, not SSE — simpler for non-browser clients, and the RPC-only
  surface (no server→client notifications yet) needs no event stream.

## Related ADRs

- `docs/adr/0037-mcp-bridge.md` — why a transport bridge, not new
  endpoints or direct agent tools.
- `docs/technical/copilot-agentic-architecture.md` §3 — the tool
  registry chokepoint this module builds on.

## CHANGELOG

See `./CHANGELOG.md`.