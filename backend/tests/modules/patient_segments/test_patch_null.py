"""An explicit ``null`` segment name is a 422, not the duplicate-name 409 (#1134)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_null_name_is_422_not_409(client, auth_headers, test_clinic):
    created = await client.post(
        "/api/v1/patient_segments/segments", json={"name": "vip"}, headers=auth_headers
    )
    assert created.status_code == 201, created.text
    seg_id = created.json()["data"]["id"]

    patched = await client.patch(
        f"/api/v1/patient_segments/segments/{seg_id}",
        json={"name": None},
        headers=auth_headers,
    )
    assert patched.status_code == 422, patched.text
    assert "name" in patched.text

    listed = await client.get("/api/v1/patient_segments/segments", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert [s["name"] for s in listed.json()["data"]] == ["vip"]
