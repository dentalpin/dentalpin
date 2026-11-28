"""A typed ``%`` or ``_`` in a search box matches literally (#1245).

Payments escaped LIKE wildcards in #1033; the other free-text searches
still built ``f"%{term}%"``, so ``%`` listed every row and ``ana_lopez``
also matched ``ana.lopez``. One ORM search (patients, through the API),
the medical-reference pickers (``.contains`` rather than ``ilike``) and
the raw-SQL one (treatment-plan pipeline) cover each form of the fix.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.medical_reference.models import ReferenceAllergy
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import TreatmentPlan
from app.modules.treatment_plan.service import TreatmentPlanService


async def _add_patients(db: AsyncSession, clinic: Clinic) -> None:
    for first, last, email in [
        ("Ana", "Lopez", "ana_lopez@example.com"),
        ("José", "Muñoz", "ana.lopez@example.com"),
        ("Anabel", "Pérez", "anaxlopez@example.com"),
    ]:
        db.add(
            Patient(id=uuid4(), clinic_id=clinic.id, first_name=first, last_name=last, email=email)
        )
    await db.commit()


async def _patient_names(client: AsyncClient, headers: dict, clinic: Clinic, search: str) -> set:
    response = await client.get(
        "/api/v1/patients",
        params={"search": search},
        headers={**headers, "X-Clinic-ID": str(clinic.id)},
    )
    assert response.status_code == 200, response.text
    return {p["first_name"] for p in response.json()["data"]}


@pytest.mark.asyncio
async def test_patient_search_treats_percent_and_underscore_literally(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    await _add_patients(db_session, test_clinic)

    assert await _patient_names(client, auth_headers, test_clinic, "%") == set()
    # A literal "_" finds only the one email that contains it.
    assert await _patient_names(client, auth_headers, test_clinic, "_") == {"Ana"}
    assert await _patient_names(client, auth_headers, test_clinic, "a%z") == set()
    # Only the address with a real underscore, not ana.lopez / anaxlopez.
    assert await _patient_names(client, auth_headers, test_clinic, "ana_lopez") == {"Ana"}
    # Plain substring search is unchanged.
    assert await _patient_names(client, auth_headers, test_clinic, "ana") == {
        "Ana",
        "José",
        "Anabel",
    }


@pytest.mark.asyncio
async def test_pipeline_search_treats_percent_and_underscore_literally(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    created_by = (
        await db_session.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Ana", last_name="Lopez")
    db_session.add(patient)
    for title in ("Fase_1 implante", "Fase.1 ortodoncia", "Limpieza"):
        db_session.add(
            TreatmentPlan(
                id=uuid4(),
                clinic_id=test_clinic.id,
                patient_id=patient.id,
                plan_number=f"PLAN-{uuid4().hex[:8]}",
                title=title,
                created_by=created_by,
                status="active",
                created_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    async def titles(search: str) -> set:
        rows, _ = await TreatmentPlanService.list_pipeline(
            db_session, test_clinic.id, "sin_cita", search=search
        )
        return {r["plan_title"] for r in rows}

    assert await titles("%") == set()
    assert await titles("Fase_1") == {"Fase_1 implante"}
    assert await titles("fase") == {"Fase_1 implante", "Fase.1 ortodoncia"}


@pytest.mark.asyncio
async def test_medical_reference_search_treats_percent_and_underscore_literally(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    for name in ("Penicilina", "Latex_A", "Latex.B"):
        db_session.add(ReferenceAllergy(id=uuid4(), clinic_id=test_clinic.id, name=name))
    await db_session.commit()

    async def names(q: str) -> set:
        response = await client.get(
            "/api/v1/medical_reference/allergies",
            params={"q": q},
            headers={**auth_headers, "X-Clinic-ID": str(test_clinic.id)},
        )
        assert response.status_code == 200, response.text
        return {a["name"] for a in response.json()["data"]}

    assert await names("%") == set()
    assert await names("_") == {"Latex_A"}
    # Case-insensitive substring search is unchanged.
    assert await names("latex") == {"Latex_A", "Latex.B"}
