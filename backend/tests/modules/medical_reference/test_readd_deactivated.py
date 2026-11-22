"""Re-adding a deactivated reference item brings it back (#963).

Deactivation hides an item from every search, including the patient
form's picker, which then offers to create it. ``create`` checked for a
duplicate name without looking at ``is_active``, so it answered 409
"already exists in this list" for a row no list showed. The medication
stayed free text with no ``reference_id``, so its interaction and
contraindication flags never fired.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .test_patient_flags import _create_reference_medication, _get_flags, _save_history

BASE = "/api/v1/medical_reference"


@pytest.mark.asyncio
async def test_readding_a_deactivated_medication_reactivates_it(
    client: AsyncClient, auth_headers: dict, test_patient
):
    warfarin_id = await _create_reference_medication(client, auth_headers, "Warfarin")
    aspirin_id = await _create_reference_medication(client, auth_headers, "Aspirin")
    res = await client.post(
        f"{BASE}/interactions",
        json={
            "medication_a_id": aspirin_id,
            "medication_b_id": warfarin_id,
            "risk_note": "Increased bleeding risk",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    res = await client.delete(f"{BASE}/medications/{warfarin_id}", headers=auth_headers)
    assert res.status_code == 204, res.text

    # The picker searches active rows only, finds nothing, offers "create".
    res = await client.get(f"{BASE}/medications", params={"q": "warf"}, headers=auth_headers)
    assert res.json()["data"] == []
    res = await client.post(f"{BASE}/medications", json={"name": "warfarin"}, headers=auth_headers)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["id"] == warfarin_id
    assert data["is_active"] is True

    res = await client.get(f"{BASE}/medications", params={"q": "warf"}, headers=auth_headers)
    assert [m["id"] for m in res.json()["data"]] == [warfarin_id]

    # The same row comes back, so its interaction rule applies again.
    await _save_history(
        client,
        auth_headers,
        test_patient.id,
        [
            {"name": "Aspirin", "reference_id": aspirin_id},
            {"name": "Warfarin", "reference_id": warfarin_id},
        ],
    )
    flags = await _get_flags(client, auth_headers, test_patient.id)
    assert [f["type"] for f in flags] == ["interaction"]


@pytest.mark.asyncio
async def test_adding_an_active_name_is_still_409(
    client: AsyncClient, auth_headers: dict, test_patient
):
    await _create_reference_medication(client, auth_headers, "Ibuprofen")
    res = await client.post(f"{BASE}/medications", json={"name": "IBUPROFEN"}, headers=auth_headers)
    assert res.status_code == 409, res.text
