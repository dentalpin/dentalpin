# 0037 — MCP bridge: reuse the tool registry, don't add another data API

- **Status:** proposed
- **Date:** 2026-09-13
- **Deciders:** backend core
- **Tags:** modules, agents, security, integrations

## Context

AI desktop clients (Claude Desktop, Cursor, …) speak the Model Context
Protocol. DentalPin already had two machine-facing surfaces: internal
agent tools (`app/core/agents/tools/`, reached by the copilot module)
and a token-authenticated public read API (`integrations/public/`, one
endpoint per resource, issue #65). Both cover patient lookups, but
neither is directly consumable by an MCP host.

Two temptations existed: (1) expose the public data API through MCP by
re-implementing read logic; (2) mount MCP directly inside the agents
core, turning an internal mechanism into an external one. Both would
create a second path to patient data with its own permission rules.

## Decision

Add a **transport-only module** (`mcp`, `depends=["patients",
"integrations"]`) that mounts an MCP streamable-HTTP server whose two
handlers (`tools/list`, `tools/call`) are thin wrappers over the
existing `tool_registry`. Tool implementations stay where they are —
the module never duplicates business logic. Access is gated by ASGI
middleware on the integrations **API tokens** (`Bearer dp_...`,
`patients:read`/`patients:write` scopes), and since this module has no
staff RBAC, no `get_permissions()` entries, no new bus events, and no
tables, it adds no namespaced surface of its own.

The curated surface is a closed, scope-admitted allowlist
(`server.CURATED_TOOLS`): `patients.search_patients`,
`patients.get_patient` (via `patients:read`) and
`patients.create_patient` (via `patients:write`). Each new scope must
exist in `integrations.triggers.SUPPORTED_TOKEN_SCOPES` before the
corresponding tool can be curated in.

Because the token (not a JWT session) is the identity, the audit trail
is keyed on deterministic `uuid5` ids derived from the token, with the
matching `agents` (`type="external_mcp"`) and `agent_sessions` rows
UPSERTed before each call — so every tool invocation from one token
groups under one stable agent/session and the registry's audit writes
(which FK on those tables) just work.

## Consequences

### Good

- **One chokepoint.** Guardrails, RBAC-tool-permission check, Pydantic
  validation, `jsonify`, and the audit log all run through
  `ToolRegistry.call` for MCP traffic exactly as for internal agents —
  no second path that can drift.
- **Zero new data logic.** Tools wrap the same services the HTTP routes
  use, so multi-tenancy (`ctx.clinic_id`) comes for free.
- **No RBAC/permission/event/table surface.** `get_permissions() = []`,
  no `EventType` additions, no real Alembic migrations — install/uninstall and
  permission modeling stay trivial, and `role_permissions` stays empty.
  (Later amendment: `removable=True` requires an isolated branch and a
  backfilled `base_revision`, so the module ships one no-op Alembic
  revision `mcp_0001` — see its `migrations/versions/` — mirroring
  `recall_reminders`. Uninstall remains a schema no-op.)
- **Scoped by-construction.** Auth reuses the proven `dp_` token
  lifecycle (hashing, revocation, `integrations.tokens.*` UI).
- **SDK-standard transport.** Any conformant MCP client connects; the
  Python SDK client is used by the contract test.

### Bad / accepted trade-offs

- The manager's `run()` is process-single-use; the lazy-start wrapper
  (`router._LazyManagedMCPApp`) is one-shot per process, so tests must
  exercise the endpoint once per process (one contract function).
- `json_response=True` diverges from SSE default — fine while the
  surface is pure RPC, needs revisiting if server→client notifications
  (e.g. progress) are added.
- Scope are permitted tools by construction: `patients:read` tokens see
  only the read tools, `patients:write` only `create_patient`, both
  scopes the full surface. `update_patient` stays out until a safe
  machine-facing write shape exists.

## Alternatives considered

- **MCP handlers calling services directly** — would duplicate the
  audit/guardrail pipeline and re-implement tool semantics; rejected.
- **Opening the internal copilot agents endpoint to MCP** — would expose
  internal mechanisms (supervision, live sessions) to external clients;
  rejected.
- **Extending `integrations/public/` with generic endpoints** — a
  per-resource REST surface can't serve the tool-calling style MCP
  clients expect; both coexist (MCP reuses tools, public API stays for
  REST automations).
- **JWT auth for MCP** — staff sessions shouldn't ride machine-to-machine
  traffic; tokens centralize revocation and scope. Rejected.
- **Per-token `agents` rows created on demand server-side** — the UPSERT
  approach chosen instead keeps ids deterministic and rebuildable.

## How to verify the rule still holds

- `tests/modules/mcp/test_server.py` — 401 gate, initialize /
  tools/list (asserts the scope-filtered curated allowlist) / read +
  write tool calls / permission-denied on a read-only token /
  revoked-token rejection.
- `tests/test_entry_point_parity.py` — the module has a pyproject entry
  point (production discovery relies on it).
- grep-able invariant: `server.CURATED_TOOLS` only references tools in
  the registry; writing tools requires a matching scope in
  `integrations/triggers.py`.

## References

- `backend/app/modules/mcp/server.py` (allowlist, delegated calls)
- `backend/app/modules/mcp/auth.py` (ASGI bearer + scope gate)
- `backend/app/modules/mcp/router.py` (lazy manager lifecycle)
- `app/core/agents/tools/registry.py` (the reused chokepoint)
- `docs/technical/copilot-agentic-architecture.md` §3