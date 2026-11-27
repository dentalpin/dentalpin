"""Re-adding a deactivated interaction or contraindication brings it back (#1236).

Deactivating a pair hides it from the settings list and from the patient
flags, and the settings page has no reactivate action. ``create_interaction``
and ``create_contraindication`` checked for a duplicate pair without
looking at ``is_active``, so adding the pair again answered 409 "already
recorded" for a row no list showed, and the warning was gone for good.
Same fix as the name lists (#963): the inactive row is reactivated, with
the risk note from the request.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .test_patient_flags import _create_reference_medication, _get_flags, _save_history

BASE = "/api/v1/medical_reference"


async def _create_disease(client: AsyncClient, auth_headers: dict, name: str) -> str:
    res = await client.post(f"{BASE}/diseases", json={"name": name}, headers=auth_headers)
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


@pytest.mark.asyncio
async def test_readding_a_deactivated_interaction_reactivates_it(
    client: AsyncClient, auth_headers: dict, test_patient
):
    warfarin_id = await _create_reference_medication(client, auth_headers, "Warfarin")
    ibuprofen_id = await _create_reference_medication(client, auth_headers, "Ibuprofen")
    res = await client.post(
        f"{BASE}/interactions",
        json={
            "medication_a_id": warfarin_id,
            "medication_b_id": ibuprofen_id,
            "risk_note": "bleeding",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    pair_id = res.json()["data"]["id"]
    await _save_history(
        client,
        auth_headers,
        test_patient.id,
        [
            {"name": "Warfarin", "reference_id": warfarin_id},
            {"name": "Ibuprofen", "reference_id": ibuprofen_id},
        ],
    )
    assert [f["type"] for f in await _get_flags(client, auth_headers, test_patient.id)] == [
        "interaction"
    ]

    res = await client.delete(f"{BASE}/interactions/{pair_id}", headers=auth_headers)
    assert res.status_code == 204, res.text
    assert await _get_flags(client, auth_headers, test_patient.id) == []

    # Entered in the opposite order: pair matching is order-insensitive.
    res = await client.post(
        f"{BASE}/interactions",
        json={
            "medication_a_id": ibuprofen_id,
            "medication_b_id": warfarin_id,
            "risk_note": "Major bleeding risk",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["id"] == pair_id
    assert data["is_active"] is True
    assert data["risk_note"] == "Major bleeding risk"

    res = await client.get(f"{BASE}/interactions", headers=auth_headers)
    assert [r["id"] for r in res.json()["data"]] == [pair_id]
    flags = await _get_flags(client, auth_headers, test_patient.id)
    assert [(f["type"], f["risk_note"]) for f in flags] == [("interaction", "Major bleeding risk")]


@pytest.mark.asyncio
async def test_readding_a_deactivated_contraindication_reactivates_it(
    client: AsyncClient, auth_headers: dict, test_patient
):
    ibuprofen_id = await _create_reference_medication(client, auth_headers, "Ibuprofen")
    hemophilia_id = await _create_disease(client, auth_headers, "Hemophilia")
    body = {"disease_id": hemophilia_id, "medication_id": ibuprofen_id, "risk_note": "no NSAIDs"}
    res = await client.post(f"{BASE}/contraindications", json=body, headers=auth_headers)
    assert res.status_code == 201, res.text
    pair_id = res.json()["data"]["id"]
    res = await client.delete(f"{BASE}/contraindications/{pair_id}", headers=auth_headers)
    assert res.status_code == 204, res.text

    res = await client.post(
        f"{BASE}/contraindications",
        json={**body, "risk_note": "Avoid NSAIDs: bleeding"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["id"] == pair_id
    assert data["is_active"] is True
    assert data["risk_note"] == "Avoid NSAIDs: bleeding"

    await _save_history(
        client,
        auth_headers,
        test_patient.id,
        [{"name": "Ibuprofen", "reference_id": ibuprofen_id}],
        diseases=[{"name": "Hemophilia", "reference_id": hemophilia_id}],
    )
    flags = await _get_flags(client, auth_headers, test_patient.id)
    assert [(f["type"], f["risk_note"]) for f in flags] == [
        ("contraindication", "Avoid NSAIDs: bleeding")
    ]


@pytest.mark.asyncio
async def test_adding_an_active_pair_is_still_409(
    client: AsyncClient, auth_headers: dict, test_patient
):
    warfarin_id = await _create_reference_medication(client, auth_headers, "Warfarin")
    ibuprofen_id = await _create_reference_medication(client, auth_headers, "Ibuprofen")
    hemophilia_id = await _create_disease(client, auth_headers, "Hemophilia")
    pair = {"medication_a_id": warfarin_id, "medication_b_id": ibuprofen_id, "risk_note": "x"}
    res = await client.post(f"{BASE}/interactions", json=pair, headers=auth_headers)
    assert res.status_code == 201, res.text
    swapped = {**pair, "medication_a_id": ibuprofen_id, "medication_b_id": warfarin_id}
    res = await client.post(f"{BASE}/interactions", json=swapped, headers=auth_headers)
    assert res.status_code == 409, res.text

    contra = {"disease_id": hemophilia_id, "medication_id": ibuprofen_id, "risk_note": "y"}
    res = await client.post(f"{BASE}/contraindications", json=contra, headers=auth_headers)
    assert res.status_code == 201, res.text
    res = await client.post(f"{BASE}/contraindications", json=contra, headers=auth_headers)
    assert res.status_code == 409, res.text
