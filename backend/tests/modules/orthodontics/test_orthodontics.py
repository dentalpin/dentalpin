"""Orthodontics slice-a: cases, controls, tenancy, seeds, HTTP codes."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.orthodontics.schemas import OrthoCaseCreate, OrthoControlCreate
from app.modules.orthodontics.service import (
    OrthoCaseService,
    OrthoControlService,
    OrthoSettingsService,
)


async def _professional(db_session, clinic_id, role="dentist"):
    user = User(
        id=uuid4(),
        email=f"ortho-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Orto",
        last_name="Doncista",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role=role))
    await db_session.commit()
    return user


def _case_data(patient_id):
    return OrthoCaseCreate(
        patient_id=patient_id,
        appliance_type="brackets_metal",
        start_date=date(2026, 1, 15),
        estimated_months=18,
    )


@pytest.mark.asyncio
async def test_case_control_lifecycle(db_session: AsyncSession, test_clinic: Clinic, test_patient):
    doc = await _professional(db_session, test_clinic.id)
    case, ann = await OrthoCaseService.create(
        db_session, test_clinic.id, _case_data(test_patient.id)
    )
    await db_session.commit()
    assert case.status == "active"
    assert ann["control_count"] == 0

    control = await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(
            upper_wire="NiTi .014",
            lower_wire="NiTi .012",
            procedures=["power_chain"],
            hygiene="good",
            next_control_weeks=4,
        ),
        performed_by=doc.id,
    )
    await db_session.commit()
    assert control.procedures == ["power_chain"]
    await db_session.refresh(case)
    assert case.current_upper_wire == "NiTi .014"
    assert case.current_lower_wire == "NiTi .012"

    # Null wires leave the in-mouth state untouched.
    await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(procedures=["ligature_change"], next_control_weeks=4),
        performed_by=doc.id,
    )
    await db_session.commit()
    await db_session.refresh(case)
    assert case.current_upper_wire == "NiTi .014"

    found = await OrthoCaseService.get(db_session, test_clinic.id, case.id)
    assert found is not None
    assert found[1]["control_count"] == 2
    assert found[1]["next_due"] is not None

    closed, _ = await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "finished", None
    )
    await db_session.commit()
    assert closed is not None and closed.finished_at is not None

    with pytest.raises(ValueError, match="finished"):
        await OrthoControlService.register(
            db_session,
            test_clinic.id,
            case.id,
            OrthoControlCreate(procedures=[]),
            performed_by=doc.id,
        )


@pytest.mark.asyncio
async def test_non_professional_rejected(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    recep = await _professional(db_session, test_clinic.id, role="receptionist")
    with pytest.raises(ValueError, match="Invalid professional"):
        await OrthoCaseService.create(
            db_session,
            test_clinic.id,
            OrthoCaseCreate(
                patient_id=test_patient.id,
                appliance_type="aligners",
                professional_id=recep.id,
            ),
        )


@pytest.mark.asyncio
async def test_tenancy_isolation(db_session: AsyncSession, test_clinic: Clinic, test_patient):
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    assert await OrthoCaseService.get(db_session, other_clinic.id, case.id) is None
    assert (
        await OrthoCaseService.list_for_patient(db_session, other_clinic.id, test_patient.id) == []
    )


@pytest.mark.asyncio
async def test_settings_seed_idempotent(db_session: AsyncSession, test_clinic: Clinic):
    first = await OrthoSettingsService.get_or_seed(db_session, test_clinic.id)
    await db_session.commit()
    assert len(first.wires) >= 10
    assert "power_chain" in first.procedures
    second = await OrthoSettingsService.get_or_seed(db_session, test_clinic.id)
    await db_session.commit()
    assert first.id == second.id
    assert await OrthoSettingsService.seed_count(db_session) >= 1


@pytest.mark.asyncio
async def test_http_codes(client, auth_headers, test_patient):
    # 201 create, 200 get, 201 control, 422 bogus enum, 404 unknown.
    response = await client.post(
        "/api/v1/orthodontics/cases",
        json={"patient_id": str(test_patient.id), "appliance_type": "aligners"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    case_id = response.json()["data"]["id"]

    response = await client.get(f"/api/v1/orthodontics/cases/{case_id}", headers=auth_headers)
    assert response.status_code == 200

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/controls",
        json={"procedures": ["ipr"], "aligner_number": 3},
        headers=auth_headers,
    )
    assert response.status_code == 201

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/status",
        json={"status": "bogus"},
        headers=auth_headers,
    )
    assert response.status_code == 422

    response = await client.get(f"/api/v1/orthodontics/cases/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404
