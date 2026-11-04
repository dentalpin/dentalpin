"""Allergy severity is a closed vocabulary: only `high` and `critical` raise
an alert, so a value outside the four known ones would silently raise none."""

import pytest
from httpx import AsyncClient

from app.modules.patients_clinical.service import PatientsClinicalService


def _base(patient) -> str:
    return f"/api/v1/patients_clinical/patients/{patient.id}"


@pytest.mark.asyncio
@pytest.mark.parametrize("severity", ["severe", "High", ""])
async def test_create_rejects_unknown_severity(
    client: AsyncClient, auth_headers: dict, test_patient, severity: str
):
    response = await client.post(
        f"{_base(test_patient)}/allergies",
        json={"name": "Penicilina", "severity": severity},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_rejects_unknown_severity(
    client: AsyncClient, auth_headers: dict, test_patient
):
    created = await client.post(
        f"{_base(test_patient)}/allergies",
        json={"name": "Penicilina", "severity": "high"},
        headers=auth_headers,
    )
    allergy_id = created.json()["data"]["id"]

    response = await client.put(
        f"{_base(test_patient)}/allergies/{allergy_id}",
        json={"severity": "severe"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_bulk_replace_rejects_unknown_severity(
    client: AsyncClient, auth_headers: dict, test_patient
):
    response = await client.put(
        f"{_base(test_patient)}/medical-history",
        json={"allergies": [{"name": "Latex", "severity": "severe"}]},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("severity", "alerts"),
    [("low", False), ("medium", False), ("high", True), ("critical", True)],
)
async def test_known_severities_are_accepted(
    client: AsyncClient, auth_headers: dict, test_patient, severity: str, alerts: bool
):
    created = await client.post(
        f"{_base(test_patient)}/allergies",
        json={"name": "Penicilina", "severity": severity},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["data"]["severity"] == severity

    response = await client.get(f"{_base(test_patient)}/alerts", headers=auth_headers)
    titles = [alert["title"] for alert in response.json()["data"]["alerts"]]
    assert any("Penicilina" in title for title in titles) is alerts


@pytest.mark.asyncio
async def test_row_stored_before_validation_stays_readable(
    client: AsyncClient, auth_headers: dict, db_session, test_patient
):
    """The API accepted any string until now, so such rows can exist."""
    await PatientsClinicalService.create_allergy(
        db_session,
        test_patient.clinic_id,
        test_patient.id,
        {"name": "Penicilina", "severity": "severe"},
    )
    await db_session.commit()

    response = await client.get(f"{_base(test_patient)}/allergies", headers=auth_headers)
    assert response.status_code == 200
    assert [row["severity"] for row in response.json()["data"]] == ["severe"]
