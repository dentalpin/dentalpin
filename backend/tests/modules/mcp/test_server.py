"""MCP module contract: token auth gate, tool advert, real tool execution.

One test function on purpose: the StreamableHTTPSessionManager behind
``/api/v1/mcp/`` is process-single-use (`run()` can only be entered once),
so a fresh event loop per pytest-asyncio test would strand the manager task
from a previous test. Keeping the whole contract in a single function means
exactly one manager start per process.
"""

import json

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
):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

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

    # --- Full streamable-HTTP session: initialize → list → call. ---------
    hx = httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://test",
        headers={"authorization": f"Bearer {dp_token}"},
        timeout=60,
    )
    try:
        async with streamable_http_client(MCP_BASE, http_client=hx) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init = await session.initialize()
                assert init.server_info.name == "dentalpin-mcp"

                listed = await session.list_tools()
                # Curated allowlist: the two read tools, nothing else.
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
    finally:
        await hx.aclose()

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
