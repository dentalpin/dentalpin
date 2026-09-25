# Changelog — mcp module

## Unreleased

### Shared token auth (rate limit + usage tracking)

- `DentalPinAuthMiddleware` now authenticates through the integrations
  module's single shared entry point (`IntegrationsService.
  authenticate_token`), which enforces the per-token fixed-window rate
  limit (60/min + 1000/day) and stamps `last_used_at`. Every MCP request
  (`initialize`, `tools/list`, `tools/call`, bad-token floods) is rate
  limited per token, and admin-visible usage shows on the token list —
  same semantics as the integrations public API. A rate-limited token
  now gets a 429 `rate_limited` JSON response from the middleware
  instead of proceeding into the app.

### Review hygiene (PR #460)

- Destroyed the stray `backend/D:/PROJECTS/...` absolute-path file
  committed under `backend/`.
- Reverted the `.gitignore` policy change to match `main` (dropped the
  `.claude/` un-ignore and the `/.kilo/plans`/`/.vs` editor-tooling rules)
  — the token-minting skill and `.kilo` config are no longer committed;
  keep them local.
- Renumbered the ADR from 0033 → 0037 (`docs/adr/0037-mcp-bridge.md`,
  `Status: proposed`) — 0033 belongs to the Poland ADR on `main`.

### Write exposure via `patients:write` scope

- Adds `patients.create_patient` to the curated server allowlist
  (`server.CURATED_TOOLS`). The token's scopes are translated to the RBAC
  grants the tools declare (`_SCOPE_TO_PERMISSION`); `tools/list` only
  surfaces tools the token could call, and every `tools/call` enforces the
  translated grants at the registry chokepoint.
- `auth.py`: the middleware gate now accepts any token carrying an
  MCP-supported scope (`MCP_SCOPES` = `patients:read` / `patients:write`)
  instead of hard-requiring `patients:read`.

### Initial MCP bridge (registration + transport)

- New optional `mcp` module (`auto_install=False`, `removable=True`,
  `depends=["patients", "integrations"]`). Transport-only: no models,
  no tables.
- Ships a single no-op Alembic revision (`mcp_0001`, own branch,
  empty upgrade/downgrade) so `removable=True` has an isolated branch
  and uninstall gets a `base_revision` to allow — same pattern as
  `recall_reminders`. Registered in `backend/alembic.ini`
  `version_locations` (M1 guard).
- Mounts the MCP `StreamableHTTPSessionManager` under `/api/v1/mcp/`
  (streamable-HTTP, `json_response=True`). A lazy ASGI wrapper starts
  the manager's `run()` task on first request — Starlette never runs a
  mounted sub-app's lifespan.
- Bare `/api/v1/mcp` (no trailing slash) 307-redirects to the slashed
  endpoint; MCP SDK clients follow it preserving method/body.

### Auth & identity

- `DentalPinAuthMiddleware` (ASGI) gates the whole surface with
  `Authorization: Bearer dp_...` (integrations API tokens via
  `IntegrationsService.authenticate_token`), enforcing the
  `patients:read` scope. 401/403 JSON, no manager touched on failure.
- Per-message identity (clinic, token, scopes) is stashed on the
  starlette request scope and read back in `tools/call`.

### Curated tool surface

- `server.py` re-exposes `patients.search_patients` and
  `patients.get_patient` through the shared `tool_registry` chokepoint —
  guardrails, RBAC, validation and audit log still enforced, no logic
  duplicated. (Initially read-only; `create_patient` shipped with the
  `patients:write` scope — see "Write exposure" above. `update_patient`
  remains out.)
- Deterministic per-token `agents`/`agent_sessions` rows (UPSERT) so
  the audit trail's FKs resolve and one token's calls group under one
  agent/session.

### Tests & docs

- `tests/modules/mcp/test_server.py` — full contract: 401 gate,
  session initialize, curated tools/list, `search_patients` +
  `get_patient`, revoked-token rejection (single process-wide session).
- Module CLAUDE.md + CHANGELOG, `docs/technical/mcp/` overview/events/
  permissions, ADR 0037, glossary entry, catalogs regenerated.
- `docs/technical/mcp/overview.md` "Trying it out": token-minting steps
  + `dp_` token lifecycle (no expiry — revoke via
  `POST /tokens/{id}/revoke`, `last_used_at` tracking), a raw JSON-RPC
  smoke sequence, a Postman walkthrough (session-id capture via Tests
  script — validated live against the demo backend), and Claude,
  Desktop/Claude Code + Kilo Code connection config (`.mcp.json`,
  `claude mcp add`, `kilo.jsonc` `skills.paths` reuse of
  `.claude/skills/`).
- `.claude/skills/mint-dp-token/SKILL.md` and `.kilo/kilo.jsonc` were
  part of the local experiment and are **not** committed to the repo —
  they are tooling for one setup and were untracked during review (see
  "Review hygiene" above). Keep them in your local tree.