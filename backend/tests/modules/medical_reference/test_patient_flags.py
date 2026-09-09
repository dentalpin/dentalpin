"""medical_reference: end-to-end coverage for GET /patients/{id}/flags.

This is the test that would have caught the upstream crash immediately:
the endpoint reads patients_clinical's Medication.reference_id /
SystemicDisease.reference_id, which only exist since the pc_0002
migration. It exercises the full path over HTTP —

1. reference medications + an interaction created through
   /api/v1/medical_reference/*,
2. a patient medical history submitted through patients_clinical's bulk
   /medical-history endpoint with entries carrying reference_id,
3. GET /api/v1/medical_reference/patients/{patient_id}/flags returning
   the expected interaction flag,

plus the contraindication path and the legacy free-text exclusion
(entries without reference_id are never matched).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_reference_medication(client: AsyncClient, auth_headers: dict, name: str) -> str:
    res = await client.post(
        "/api/v1/medical_reference/medications",
        json={"name": name},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _save_history(
    client: AsyncClient, auth_headers: dict, patient_id, medications, diseases=()
):
    res = await client.put(
        f"/api/v1/patients_clinical/patients/{patient_id}/medical-history",
        json={"medications": medications, "systemic_diseases": list(diseases)},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text


async def _get_flags(client: AsyncClient, auth_headers: dict, patient_id) -> list[dict]:
    res = await client.get(
        f"/api/v1/medical_reference/patients/{patient_id}/flags",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


@pytest.mark.asyncio
async def test_two_interacting_reference_linked_medications_flag(
    client: AsyncClient, auth_headers: dict, test_patient
):
    """The reviewer's exact scenario: a patient on two interacting
    reference-linked medications → one interaction flag returned."""
    warfarin_id = await _create_reference_medication(client, auth_headers, "Warfarin")
    aspirin_id = await _create_reference_medication(client, auth_headers, "Aspirin")

    res = await client.post(
        "/api/v1/medical_reference/interactions",
        json={
            "medication_a_id": aspirin_id,
            "medication_b_id": warfarin_id,
            "risk_note": "Increased bleeding risk",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text

    # Pair entered in canonical order in the UI; submit history with both
    # medications linked to their reference rows.
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
    assert len(flags) == 1
    flag = flags[0]
    assert flag["type"] == "interaction"
    assert sorted(flag["involved"]) == ["Aspirin", "Warfarin"]
    assert flag["risk_note"] == "Increased bleeding risk"


@pytest.mark.asyncio
async def test_contraindication_and_free_text_exclusion(
    client: AsyncClient, auth_headers: dict, test_patient
):
    """Disease × medication contraindication flags; free-text-only legacy
    entries (no reference_id) are silently excluded."""
    ibuprofen_id = await _create_reference_medication(client, auth_headers, "Ibuprofen")

    res = await client.post(
        "/api/v1/medical_reference/diseases",
        json={"name": "Hypertension"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    hypertension_id = res.json()["data"]["id"]

    res = await client.post(
        "/api/v1/medical_reference/contraindications",
        json={
            "disease_id": hypertension_id,
            "medication_id": ibuprofen_id,
            "risk_note": "Raises blood pressure",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text

    # One linked medication + one linked disease + one free-text
    # medication that must NOT match anything.
    await _save_history(
        client,
        auth_headers,
        test_patient.id,
        [
            {"name": "Ibuprofen", "reference_id": ibuprofen_id},
            {"name": "Some untracked supplement"},  # legacy free text
        ],
        diseases=[{"name": "Hypertension", "reference_id": hypertension_id}],
    )

    flags = await _get_flags(client, auth_headers, test_patient.id)
    assert len(flags) == 1
    flag = flags[0]
    assert flag["type"] == "contraindication"
    assert flag["involved"] == ["Hypertension", "Ibuprofen"]
    assert flag["risk_note"] == "Raises blood pressure"


@pytest.mark.asyncio
async def test_no_flags_for_unlinked_history(client: AsyncClient, auth_headers: dict, test_patient):
    """A patient whose entire history is free-text-only produces no flags
    (and no error) — the pre-integration behavior stays intact."""
    await _create_reference_medication(client, auth_headers, "Warfarin")
    await _create_reference_medication(client, auth_headers, "Aspirin")

    await _save_history(
        client,
        auth_headers,
        test_patient.id,
        [{"name": "Warfarin"}, {"name": "Aspirin"}],
    )

    flags = await _get_flags(client, auth_headers, test_patient.id)
    assert flags == []


@pytest.mark.asyncio
async def test_archived_medications_do_not_flag(
    client: AsyncClient, auth_headers: dict, test_patient
):
    """History saves archive superseded rows (pc_0003); flags must only
    read the active set, otherwise a dropped medication keeps warning."""
    med_a = await _create_reference_medication(client, auth_headers, "Warfarina")
    med_b = await _create_reference_medication(client, auth_headers, "Aspirina")
    res = await client.post(
        "/api/v1/medical_reference/interactions",
        json={"medication_a_id": med_a, "medication_b_id": med_b, "risk_note": "Sangrado"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    meds = [
        {"name": "Warfarina", "reference_id": med_a},
        {"name": "Aspirina", "reference_id": med_b},
    ]
    await _save_history(client, auth_headers, test_patient.id, meds)
    assert len(await _get_flags(client, auth_headers, test_patient.id)) == 1

    await _save_history(client, auth_headers, test_patient.id, meds[:1])
    assert await _get_flags(client, auth_headers, test_patient.id) == []
