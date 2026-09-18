---
module: mcp
last_verified_commit: d9d8ad97
---

# mcp — overview

Model Context Protocol bridge. Exposes a curated, scope-gated slice of
DentalPin's agent tools to external AI clients (Claude Desktop, Cursor,
any MCP-compatible host) over the standard streamable-HTTP transport at
`/api/v1/mcp/`.

## What it is

A transport-only module (`BaseModule` with no models, no tables, no
Alembic branch). It mounts the MCP Server SDK's
`StreamableHTTPSessionManager` behind ASGI auth middleware and two
handlers:

- `tools/list` — the curated allowlist (`server.CURATED_TOOLS`),
  filtered to the tools the token's scopes admit: `patients:read`
  surfaces `search_patients` and `get_patient`; `patients:write` adds
  `create_patient`.
- `tools/call` — every call is delegated to
  `tool_registry.call(ctx, "patients.<name>", args)`, the **same single
  chokepoint** internal agents use: guardrails, RBAC permission check
  (the token's scopes are translated to the RBAC strings the tools
  declare), Pydantic validation, and the audit log all still run.

Tools are *not* reimplemented. The MCP layer is pure plumbing — a new
transport over existing tool handlers.

## Auth

No JWT, no staff session. `DentalPinAuthMiddleware` (`auth.py`) requires
`Authorization: Bearer dp_...` — the API tokens the integrations module
issues (`integrations.tokens.*`, `ApiToken` rows, SHA-256 hashed). It
requires the token to carry at least one MCP-supported scope (`MCP_SCOPES`
in `auth.py`: `patients:read`, `patients:write`; 403 otherwise) and
stashes the resolved identity (clinic id, token id, scopes) on the request
scope for the tool handler to read per message.

Unauthenticated / revoked-token traffic is rejected with 401 *before*
the session manager task ever starts.

## Endpoint shape

- Real surface: `/api/v1/mcp/` (trailing slash). The app sets
  `redirect_slashes=False`, so the bare path would 404 — the router adds
  a tiny 307 redirect at `/api/v1/mcp` that MCP SDK clients follow while
  preserving method + POST body.
- Responses are `application/json` (`json_response=True`): the surface
  is pure RPC (no server→client notifications yet), so there is nothing
  the SSE channel would carry.
- Client URL to configure: `http://<host>/api/v1/mcp/`,
  headers `Authorization: Bearer dp_...`.

## Trying it out

Prerequisites: the `mcp` module is installed (check
`./bin/dentalpin modules list` shows `mcp ... installed`), the backend
container is up (`0.0.0.0:8000->8000`), and the demo DB is seeded. The
steps below were validated against a live demo install.

### 1. Mint an API token

MCP does **not** use the staff JWT — it needs a `dp_` API token from the
integrations module. A token with `patients:read` gets the two read tools;
adding `patients:write` also exposes `create_patient`. Log in once as an
admin to issue it (the token prints **once**; store it):

```bash
# Admin login → access token (OAuth2 form, not JSON)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin@demo.clinic&password=demo1234"
# → {"access_token":"...jwt...","token_type":"bearer",...}

# Mint a read-only API token with that JWT
curl -s -X POST http://localhost:8000/api/v1/integrations/tokens \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name":"mcp-test","scopes":["patients:read"]}'
# → {"data":{"token":"dp_...", ...}}   ← save it
```

Error surface on the MCP endpoint (both return JSON, `www-authenticate:
Bearer`):

- missing / invalid / revoked token → `401 {"error":"invalid_token",...}`;
- token without any supported scope → `403
  {"error":"insufficient_scope","error_description":"Required scopes:
  patients:read, patients:write"}`.

**Token lifecycle:** `dp_` tokens never expire — the `ApiToken` row has a
`revoked_at` but no TTL, and `authenticate_token` only rejects revoked or
unknown hashes. They stay valid until manually revoked (like a Stripe or
GitHub machine key), so revoke any you stop using. `last_used_at` is
stamped on every authenticated call, which makes stale tokens easy to
spot. Revocation is staff-authenticated (JWT +
`integrations.tokens.write`):

```bash
curl -s -X POST http://localhost:8000/api/v1/integrations/tokens/<token_id>/revoke \
  -H "Authorization: Bearer <jwt>"
# → 409 Conflict if the token was already revoked
```

The `mint-dp-token` skill (`.claude/skills/`) wraps both mint and revoke.

### 2. Raw JSON-RPC smoke test (no GUI)

Streamable HTTP is a sessioned handshake: every request carries
`Authorization`, and the `initialize` response returns a
`Mcp-Session-Id` header that all later POSTs must echo.

```bash
BASE=http://localhost:8000/api/v1/mcp/
TOK=dp_...
CT='Content-Type: application/json'
ACCEPT='Accept: application/json, text/event-stream'

# 1) initialize — capture Mcp-Session-Id from the response headers
curl -s -D - -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'

# 2) notifications/initialized + tools/list (reuse SID + $TOK)
SID=<Mcp-Session-Id from step 1>
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 3) tools/call — search, then get_patient with an id from the result
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_patients","arguments":{"query":"Daniel Garcia","limit":5}}}'
curl -s -X POST "$BASE" -H "Authorization: Bearer $TOK" -H "Mcp-Session-Id: $SID" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_patient","arguments":{"patient_id":"<uuid>"}}}'
```

Responses are `application/json` (see `json_response=True` above) with
`structuredContent` plus a human-readable `text` member. On Windows
PowerShell, inline `-d` bodies get their quotes mangled — write each body
to a temp file and pass `--data "@body.json"` instead.

### 3. Postman

Same handshake, five POSTs. Create a Postman collection with these
requests (all to `http://localhost:8000/api/v1/mcp/` — keep the trailing
slash; the bare path 307-redirects and Postman may not follow it).

Common settings per request:

| Setting | Value |
|---------|-------|
| Method | `POST` |
| URL | `http://localhost:8000/api/v1/mcp/` |
| Authorization | `Bearer dp_...` (unknown/revoked → 401; missing an MCP-supported scope → 403) |
| Headers | `Content-Type: application/json`, `Accept: application/json, text/event-stream`, and (steps 2–5) `Mcp-Session-Id: {{SID}}` |
| Body | `raw` → `JSON` |

1. **initialize** — `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"postman","version":"1.0"}}}`. The response *header* `Mcp-Session-Id` starts the session; capture it automatically with a **Tests** script:

   ```js
   pm.test('capture session id', () => {
     const sid = pm.response.headers.get('Mcp-Session-Id');
     pm.expect(sid).to.not.be.undefined;
     pm.collectionVariables.set('SID', sid);
   });
   ```

   then use `{{SID}}` in the `Mcp-Session-Id` header of the requests below.

2. **notifications/initialized** — `{"jsonrpc":"2.0","method":"notifications/initialized"}`.

3. **tools/list** — `{"jsonrpc":"2.0","id":2,"method":"tools/list"}` → with a `patients:read` token returns `search_patients` + `get_patient` with their input schemas.

4. **tools/call → search_patients** — `{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_patients","arguments":{"query":"Daniel Garcia","limit":5}}}` → a patient list in `result.structuredContent`.

5. **tools/call → get_patient** — `{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_patient","arguments":{"patient_id":"<uuid from step 4>"}}}` → the patient's details.

If a request fails a session must be re-established: re-run step 1 (new `Mcp-Session-Id`).

### 4. Claude (Desktop & Code)

The endpoint is standard streamable-HTTP MCP, so both Claude apps can
dial it directly. Both need the token sent as an `Authorization: Bearer`
header — use the one minted in §1.

#### Claude Desktop (GUI)

Add a remote server to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dentalpin": {
      "type": "http",
      "url": "http://localhost:8000/api/v1/mcp/",
      "headers": {
        "Authorization": "Bearer dp_..."
      }
    }
  }
}
```

Fully quit and restart Claude Desktop (headers are read at launch, a
reload in Settings → Developers does not pick them up). Then in a chat:
*"list the MCP tools available to you"* to confirm the connection, and
*"search patients for Daniel Garcia"* to run one. If tools keep failing
with 401 auth, the Desktop build is dropping the custom header — fall
back to Claude Code.

#### Claude Code (CLI)

Register the server (default scope `local`; add `--scope project` to
share it with the team via the repo's `.mcp.json`):

```bash
claude mcp add dentalpin --transport http http://localhost:8000/api/v1/mcp/ \
  --header "Authorization: Bearer dp_..." [--scope local]
claude mcp list    # should show dentalpin as connected/OK
```

Project-scope alternative — commit `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "dentalpin": {
      "type": "http",
      "url": "http://localhost:8000/api/v1/mcp/",
      "headers": { "Authorization": "Bearer dp_..." }
    }
  }
}
```

Then prompt e.g. *"use the dentalpin MCP server: search for patient
Daniel Garcia, then fetch the details of the first result."* You should
see the read tools `search_patients` (`{query, limit}`) and
`get_patient` (`{patient_id}`); if the token also carries `patients:read`
+ `patients:write`, `create_patient` appears too.

### 5. Kilo Code

Kilo Code reads MCP servers from the top-level `mcp` key of `kilo.jsonc`
(project: `./kilo.jsonc` or `.kilo/kilo.jsonc`; global:
`~/.config/kilo/kilo.jsonc`). The repo ships `.kilo/kilo.jsonc`; mint a
token (skill `mint-dp-token` in `.kilo/skills/` or `.claude/skills/`,
or §1) and paste it in:

```jsonc
{
  "mcp": {
    "dentalpin": {
      "type": "remote",
      "url": "http://localhost:8000/api/v1/mcp/",
      "headers": { "Authorization": "Bearer dp_..." },
      "enabled": true,
      "timeout": 15000
    }
  }
}
```

Then reload the VS Code window (Kilo discovers MCP config on load) or, on
the CLI, check `kilo mcp list`. Test in Kilo chat: *"use the dentalpin
MCP server: search for patient Daniel Garcia."*

Skills: Kilo implements the open Agent Skills format and reads the same
`mint-dp-token` skill from `.claude/skills/`, wired via `skills.paths`
in the shipped `.kilo/kilo.jsonc` (no undocumented "Claude Code
Compatibility" toggle needed):

```jsonc
{
  "skills": { "paths": [".claude/skills"] }
}
```

Trigger it with *"use your mint-dp-token skill to mint a dp_ token"*.

### 6. Verify the audit trail

Every `tools/call` creates deterministic per-token
`agents`/`agent_sessions` rows (`type = 'external_mcp'`) and an
`agent_audit_logs` row, so a token's whole history groups under one
agent/session:

```bash
docker compose exec -T db psql -U dental -d dental_clinic \
  -c "SELECT name, type FROM agents WHERE type='external_mcp' ORDER BY created_at DESC LIMIT 5;" \
  -c "SELECT count(*) FROM agent_audit_logs;"
```

## Manager lifecycle

Starlette never runs the lifespan of a *mounted* sub-app, and the MCP
manager's `run()` asynccontextmanager is what spawns the per-session
task group. `router._LazyManagedMCPApp` starts `manager.run()` in a
background task on the first request and keeps it for the process
lifetime. Each `build_mcp_router()` call builds a fresh manager — the
manager is single-use, so a router instance is one-shot per process
(which tests rely on: the endpoint is exercised once per process).

## Audit trail

`tool_registry.call` writes `agent_audit_logs` rows keyed on
`agent_id`/`session_id` (both FKs). The MCP handler derives both
deterministically from the API token (`uuid5` over fixed namespaces)
and UPSERTs the corresponding `agents` (type `external_mcp`) and
`agent_sessions` rows before the call, so:

- every tool invocation from one token groups under one agent/session;
- the ids are stable across restarts;
- nothing in the registry required change to serve MCP traffic.

## Tenancy

The clinic comes from the token's own `clinic_id` (no
`get_clinic_context`). The underlying tools filter by `ctx.clinic_id`,
so a token can only ever reach its own clinic's data. The agent/session
rows are clinic-scoped too.

## Constraints

- Depends on `patients` (tool owners) and `integrations` (token
  issuance/verification). No other cross-module imports.
- No staff RBAC permissions (`get_permissions()` → `[]`): this boundary
  is scope-based, not role-based.
- The curated set is deliberately closed; each tool is admitted by a
  specific token scope (`patients:read` → `search_patients` /
  `get_patient`, `patients:write` → `create_patient`). Expanding the
  surface requires the matching scope to exist in
  `integrations/triggers.py` `SUPPORTED_TOKEN_SCOPES`.

See [`./permissions.md`](./permissions.md) and
[`./events.md`](./events.md) for the full detail, and
`backend/app/modules/mcp/CLAUDE.md` for the design rationale.