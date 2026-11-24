"""An explicit ``null`` on a NOT NULL orthodontics field is a 422 (#1134).

``procedures`` is a JSONB NOT NULL column: SQLAlchemy stores Python ``None``
as JSON ``'null'``, so a null used to commit and then break the response
model and every later list of the case's controls (500). ``appliance_type``
null on a case reached the NOT NULL column.
"""

from __future__ import annotations

import pytest


async def _case(client, auth_headers, patient_id):
    response = await client.post(
        "/api/v1/orthodontics/cases",
        json={"patient_id": patient_id, "appliance_type": "aligners"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_null_procedures_is_422_and_controls_still_list(client, auth_headers, test_patient):
    case_id = await _case(client, auth_headers, str(test_patient.id))
    control = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/controls",
        json={"procedures": ["ipr"]},
        headers=auth_headers,
    )
    assert control.status_code == 201, control.text
    control_id = control.json()["data"]["id"]

    patched = await client.patch(
        f"/api/v1/orthodontics/controls/{control_id}",
        json={"procedures": None},
        headers=auth_headers,
    )
    assert patched.status_code == 422, patched.text
    assert "procedures" in patched.text

    listed = await client.get(
        f"/api/v1/orthodontics/cases/{case_id}/controls", headers=auth_headers
    )
    assert listed.status_code == 200, listed.text
    assert [c["procedures"] for c in listed.json()["data"]] == [["ipr"]]


@pytest.mark.asyncio
async def test_null_appliance_type_is_422(client, auth_headers, test_patient):
    case_id = await _case(client, auth_headers, str(test_patient.id))

    patched = await client.patch(
        f"/api/v1/orthodontics/cases/{case_id}",
        json={"appliance_type": None},
        headers=auth_headers,
    )
    assert patched.status_code == 422, patched.text
    assert "appliance_type" in patched.text

    fetched = await client.get(f"/api/v1/orthodontics/cases/{case_id}", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["appliance_type"] == "aligners"
