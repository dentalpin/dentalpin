"""MCP module contract: token auth gate, scope-filtered tool advert, real tool execution.

One test function on purpose: the StreamableHTTPSessionManager behind
``/api/v1/mcp/`` is process-single-use (`run()` can only be entered once),
so a fresh event loop per pytest-asyncio test would strand the manager task
from a previous test. Keeping the whole contract in a single function means
exactly one manager start per process.
"""

import json
from contextlib import asynccontextmanager

import httpx2
import pytest
from httpx import AsyncClient

from app.main import app

TOKENS_BASE = "/api/v1/integrations/tokens"
MCP_BASE = "/api/v1/mcp/"


@pytest.mark.asyncio
async def test_mcp_contract(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_clinic,
    test_patient,
    monkeypatch,
):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    @asynccontextmanager
    async def mcp_session(token: str):
        """One streamable-HTTP MCP session authenticated by ``token``."""
        hx = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
            headers={"authorization": f"Bearer {token}"},
            timeout=60,
        )
        try:
            async with streamable_http_client(MCP_BASE, http_client=hx) as (
                read_stream,
                write_stream,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    yield session
        finally:
            await hx.aclose()

    async def mint_token(name: str, scopes: list[str]) -> str:
        made = await client.post(
            TOKENS_BASE,
            json={"name": name, "scopes": scopes},
            headers=auth_headers,
        )
        assert made.status_code == 201, made.text
        return made.json()["data"]["token"]

    # --- Auth gate: no token is rejected before any MCP handling. --------
    anon = await client.post(
        MCP_BASE,
        headers={"accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert anon.status_code == 401

    created = await client.post(
        TOKENS_BASE,
        json={"name": "test-mcp", "scopes": ["patients:read"]},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    dp_token = created.json()["data"]["token"]
    token_id = created.json()["data"]["id"]

    # --- Read-scoped token: read tools only, writes invisible + denied. --
    async with mcp_session(dp_token) as session:
        init = await session.initialize()
        assert init.server_info.name == "dentalpin-mcp"

        listed = await session.list_tools()
        # Curated allowlist filtered by scope: the two read tools, nothing else.
        assert sorted(t.name for t in listed.tools) == [
            "get_patient",
            "search_patients",
        ]

        found = await session.call_tool("search_patients", {"query": "Test Patient"})
        assert found.is_error is False
        payload = json.loads(found.content[0].text)
        assert payload["total"] >= 1
        names = {p["full_name"] for p in payload["patients"]}
        assert "Test Patient" in names

        one = await session.call_tool("get_patient", {"patient_id": str(test_patient.id)})
        assert one.is_error is False
        detail = json.loads(one.content[0].text)
        assert detail["full_name"] == "Test Patient"

        # A read-only token is refused the write even if it guesses the name.
        denied = await session.call_tool(
            "create_patient", {"first_name": "Jane", "last_name": "Doe"}
        )
        assert denied.is_error is True
        assert "permission denied" in denied.content[0].text

    # --- Usage tracking: the shared helper stamps last_used_at -----------
    listed = (await client.get(TOKENS_BASE, headers=auth_headers)).json()["data"]
    used = next(t for t in listed if t["id"] == str(token_id))
    assert used["last_used_at"] is not None

    # --- Write-scoped token: create_patient visible and executable. ------
    dp_write = await mint_token("test-mcp-write", ["patients:write"])
    async with mcp_session(dp_write) as session:
        await session.initialize()
        listed = await session.list_tools()
        assert [t.name for t in listed.tools] == ["create_patient"]

        made = await session.call_tool(
            "create_patient",
            {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.org"},
        )
        assert made.is_error is False
        created_id = json.loads(made.content[0].text)["id"]
        assert created_id

    # --- Both scopes: the full curated surface, incl. reading the new row.
    dp_both = await mint_token("test-mcp-both", ["patients:read", "patients:write"])
    async with mcp_session(dp_both) as session:
        await session.initialize()
        listed = await session.list_tools()
        assert sorted(t.name for t in listed.tools) == [
            "create_patient",
            "get_patient",
            "search_patients",
        ]

        detail = await session.call_tool("get_patient", {"patient_id": created_id})
        assert detail.is_error is False
        assert json.loads(detail.content[0].text)["full_name"] == "Ada Lovelace"

    # --- Revoked token can no longer open a session. ----------------------
    revoked = await client.post(
        f"{TOKENS_BASE}/{token_id}/revoke",
        headers=auth_headers,
    )
    assert revoked.status_code == 200

    gone = await client.post(
        MCP_BASE,
        headers={
            "accept": "application/json, text/event-stream",
            "authorization": f"Bearer {dp_token}",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert gone.status_code == 401

    # --- Rate limit: shared with integrations, enforced by the middleware.
    from app.modules.integrations import service as integrations_service

    monkeypatch.setattr(integrations_service, "RATE_LIMIT_PER_MINUTE", 2)
    limited_token = await mint_token("test-mcp-limited", ["patients:read"])
    limited_headers = {
        "accept": "application/json, text/event-stream",
        "authorization": f"Bearer {limited_token}",
    }
    for _ in range(2):
        hit = await client.post(
            MCP_BASE, headers=limited_headers, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
        )
        assert hit.status_code != 429, hit.text
    over = await client.post(
        MCP_BASE, headers=limited_headers, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
    )
    assert over.status_code == 429
    assert "rate_limited" in over.text
