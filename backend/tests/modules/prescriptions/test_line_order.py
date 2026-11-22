"""Prescription lines keep the order they were entered in (#966).

``PrescriptionItemCreate.sort_order`` defaulted to 0, so the service's
"fall back to the list position" branch never ran. The editor sends
``sort_order`` only for lines that came from a template or an existing
draft; a line added below them was stored with 0 and printed second.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.modules.patients.models import Patient


def _names(body: dict) -> list[str]:
    return [i["medication_name"] for i in body["data"]["items"]]


@pytest.mark.asyncio
async def test_a_line_added_after_a_template_stays_last(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
):
    pid = str(test_patient.id)
    # applyTemplate numbers the template lines; addLine sends none.
    items = [
        {"medication_name": "Amoxicilina", "sort_order": 0},
        {"medication_name": "Ibuprofeno", "sort_order": 1},
        {"medication_name": "Paracetamol"},
    ]
    created = await client.post(
        f"/api/v1/prescriptions/patients/{pid}/prescriptions",
        json={"patient_id": pid, "items": items},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    assert _names(created.json()) == ["Amoxicilina", "Ibuprofeno", "Paracetamol"]

    # Editing the draft resends the stored lines with their sort_order
    # (0, 1, 2); drop the first and add one at the bottom.
    stored = created.json()["data"]["items"]
    edited = [
        {"medication_name": i["medication_name"], "sort_order": i["sort_order"]} for i in stored[1:]
    ] + [{"medication_name": "Omeprazol"}]
    patched = await client.patch(
        f"/api/v1/prescriptions/prescriptions/{created.json()['data']['id']}",
        json={"items": edited},
        headers=auth_headers,
    )
    assert patched.status_code == 200, patched.text
    assert _names(patched.json()) == ["Ibuprofeno", "Paracetamol", "Omeprazol"]
