"""nav_online settings + records API: write-only secrets, enable gate."""

import pytest
from httpx import AsyncClient

SETTINGS = "/api/v1/nav_online/settings"
_CREDS = {
    "tax_number": "12345678",
    "technical_user_login": "t",
    "technical_user_password": "p",
    "signature_key": "s",
    "exchange_key": "0123456789abcdef",
}


@pytest.mark.asyncio
async def test_settings_roundtrip_secrets_write_only(
    client: AsyncClient, auth_headers, test_clinic
):
    res = await client.get(SETTINGS, headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["enabled"] is False
    res = await client.put(SETTINGS, json={"environment": "test", **_CREDS}, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["has_password"] and body["has_signature_key"] and body["has_exchange_key"]
    assert "technical_user_password" not in body and "signature_key" not in body


@pytest.mark.asyncio
async def test_enable_requires_complete_credentials(client: AsyncClient, auth_headers, test_clinic):
    res = await client.put(SETTINGS, json={"enabled": True}, headers=auth_headers)
    assert res.status_code == 400
    await client.put(SETTINGS, json=_CREDS, headers=auth_headers)
    res = await client.put(SETTINGS, json={"enabled": True}, headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["enabled"] is True


@pytest.mark.asyncio
async def test_exchange_key_must_be_16_chars(client: AsyncClient, auth_headers, test_clinic):
    res = await client.put(SETTINGS, json={"exchange_key": "short"}, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_records_list_empty(client: AsyncClient, auth_headers, test_clinic):
    res = await client.get("/api/v1/nav_online/records", headers=auth_headers)
    assert res.status_code == 200 and res.json()["total"] == 0
