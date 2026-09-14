---
name: mint-dp-token
description: Mint or revoke a DentalPin dp_ API token (integrations module) that authenticates the MCP endpoint /api/v1/mcp/ and the public data API. Use whenever the user asks for a dp_ token, an API/MCP credential, or help connecting an MCP client (Claude Desktop, Claude Code, Cursor, Postman) to a running DentalPin backend, and to verify or revoke an existing token.
---

# Mint a DentalPin `dp_` API token

The MCP endpoint (`/api/v1/mcp/`) and the public data API authenticate with
machine tokens `dp_...` issued by the integrations module — never a staff JWT.
This skill mints one and hands the plaintext to the user (it prints once).

## Prerequisites

- A running backend (default `http://localhost:8000`) with the `mcp` and
  `integrations` modules installed and the DB seeded.
- A staff login holding `integrations.tokens.write`. On the demo DB use
  `admin@demo.clinic` / `demo1234`. In production, ask the user for
  credentials — never invent any.

## Steps

Base URL origin: `http://localhost:8000` unless told otherwise.

### 1. Log in as staff (form-encoded)

```bash
BASE=http://localhost:8000
curl -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin@demo.clinic&password=demo1234"
# → {"access_token":"...jwt...","token_type":"bearer",...}
```

Grab the JWT from `access_token`. It is a staff credential — pass it in the
`Authorization: Bearer <jwt>` header below, but don't print it unless asked.

### 2. Mint the token

```bash
curl -s -X POST "$BASE/api/v1/integrations/tokens" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"mcp-claude","scopes":["patients:read"]}'
# → {"data":{"token":"dp_...", ...}}   ← plaintext, shown once
```

Response `data.token` is the plaintext `dp_...`. Show it to the user and explain
it is displayed once. Stow it where they ask (Claude Desktop
`claude_desktop_config.json`, `claude mcp add --header`, a repo `.mcp.json`, a
password manager). **Never write the token into any file that gets committed,
never paste it into docs, commits, or chat-visible artifacts.**

The MCP surface requires the `patients:read` scope on the token
(`backend/app/modules/mcp/auth.py`). Token API: `GET /tokens` lists,
`POST /tokens` mints, `POST /tokens/{id}/revoke` revokes — all under
`integrations.tokens.*` permissions (see `backend/app/modules/integrations/router.py`).

### 3. (Optional) Verify against MCP

```bash
curl -s -D - -X POST "$BASE/api/v1/mcp/" \
  -H "Authorization: Bearer dp_..." \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"mint-dp-token","version":"1.0"}}}'
# Expect 200 + a Mcp-Session-Id response header; follow with tools/list.
```

### 4. (Optional) Revoke when no longer needed

```bash
curl -s -X POST "$BASE/api/v1/integrations/tokens/$TOKEN_ID/revoke" \
  -H "Authorization: Bearer $JWT"
# 409 Conflict if already revoked.
```

## Error surface

| Symptom | Meaning | Fix |
|---|---|---|
| `401` from `/auth/login` | wrong staff credentials | correct username/password |
| `403` on token create | role lacks `integrations.tokens.write` | use an admin account |
| `401 invalid_token` from `/api/v1/mcp/` | missing / invalid / revoked `dp_` token | mint a fresh one |
| `403 insufficient_scope` from `/api/v1/mcp/` | token lacks `patients:read` | mint again with the scope |

Windows/PowerShell: inline `-d` bodies get quotes mangled — write the body to a
temp file and pass `--data "@body.json"`.

## Config examples (once the token exists)

Both clients just need an `Authorization: Bearer dp_...` header:

- **Claude Code**:
  `claude mcp add dentalpin --transport http http://localhost:8000/api/v1/mcp/ --header "Authorization: Bearer dp_..."`
- **Claude Desktop**: add to `claude_desktop_config.json` under `mcpServers`:
  `"type": "http"`, `"url": "http://localhost:8000/api/v1/mcp/"`,
  `"headers": { "Authorization": "Bearer dp_..." }`.

Full walkthrough: `docs/technical/mcp/overview.md` (§1 mint, §4 Claude, §5 Kilo).