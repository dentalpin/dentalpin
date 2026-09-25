"""The public intake endpoint: key gate, honeypot, cap, D12 response."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic
from app.modules.leads.models import Lead, LeadIntakeKey, LeadSettings
from app.modules.leads.service import LeadIntakeKeyService
from app.modules.patients.models import Patient
from app.modules.recalls.models import Recall

from .conftest import make_clinic, make_patient

INTAKE = "/api/v1/leads/public/intake"

PAYLOAD = {
    "full_name": "Marta Ruiz",
    "phone": "+34 699 888 777",
    "email": "marta@example.com",
    "motive": "Presupuesto de ortodoncia",
    "description": "Viene de Instagram.",
    "availability_days": ["tue", "thu"],
    "availability_slot": "afternoon",
}


async def _mint_key(db: AsyncSession, clinic_id) -> str:
    _, plaintext = await LeadIntakeKeyService.rotate(db, clinic_id)
    await db.commit()
    return plaintext


async def _day_count_from_a_fresh_connection(clinic_id) -> int:
    """Read the gauge the way production would: a new session, no shared
    identity map, no optimistic in-memory value."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as session:
            row = (
                await session.execute(
                    select(LeadSettings).where(LeadSettings.clinic_id == clinic_id)
                )
            ).scalar_one()
            return int(row.day_count)
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Key gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_key_creates_the_lead(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    key = await _mint_key(db_session, test_clinic.id)

    response = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": key})

    assert response.status_code == 201, response.text
    assert response.json() == {"data": {"received": True}, "message": None}

    leads = list(
        (await db_session.execute(select(Lead).where(Lead.clinic_id == test_clinic.id))).scalars()
    )
    assert len(leads) == 1
    assert leads[0].phone == PAYLOAD["phone"]

    # The key was touched, and today's counter moved.
    stored = (
        await db_session.execute(
            select(LeadIntakeKey).where(LeadIntakeKey.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    assert stored.last_used_at is not None
    usage = (
        await db_session.execute(
            select(LeadSettings).where(LeadSettings.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    assert usage.day_count == 1


@pytest.mark.asyncio
async def test_missing_unknown_and_inactive_keys_are_indistinguishable(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    """One generic 401: the caller must not learn which case it hit."""
    key = await _mint_key(db_session, test_clinic.id)

    missing = await client.post(INTAKE, json=PAYLOAD)
    unknown = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": "lk_nope"})

    key_row = (
        await db_session.execute(
            select(LeadIntakeKey).where(LeadIntakeKey.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    key_row.is_active = False
    await db_session.commit()
    inactive = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": key})

    assert missing.status_code == unknown.status_code == inactive.status_code == 401
    assert missing.content == unknown.content == inactive.content

    assert (
        await db_session.execute(select(Lead).where(Lead.clinic_id == test_clinic.id))
    ).scalars().all() == []


# ---------------------------------------------------------------------------
# Cheap rejections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honeypot_answers_success_and_writes_nothing(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    key = await _mint_key(db_session, test_clinic.id)
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    response = await client.post(
        INTAKE,
        json={**PAYLOAD, "phone": "600111222", "website": "http://spam.example"},
        headers={"X-Lead-Key": key},
    )

    assert response.status_code == 201
    assert response.json() == {"data": {"received": True}, "message": None}
    assert (
        await db_session.execute(select(Lead).where(Lead.clinic_id == test_clinic.id))
    ).scalars().all() == []
    assert (
        await db_session.execute(select(Recall).where(Recall.patient_id == patient.id))
    ).scalars().all() == []


@pytest.mark.asyncio
async def test_validation_failure_is_422(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    key = await _mint_key(db_session, test_clinic.id)
    response = await client.post(
        INTAKE, json={**PAYLOAD, "motive": ""}, headers={"X-Lead-Key": key}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_retired_free_text_availability_is_rejected(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    """Availability became structured (day codes + slot). A website still
    posting the old free-text string must be told, not quietly ignored."""
    key = await _mint_key(db_session, test_clinic.id)
    response = await client.post(
        INTAKE,
        json={**PAYLOAD, "availability": "Tardes a partir de las 17:00"},
        headers={"X-Lead-Key": key},
    )
    assert response.status_code == 422

    # …and the same payload without the stale field still works.
    accepted = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": key})
    assert accepted.status_code == 201


@pytest.mark.asyncio
async def test_oversized_body_is_413(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    """The declared-size ceiling fires before validation, so a huge body
    is a 413 (not a 422 from the field max_length)."""
    key = await _mint_key(db_session, test_clinic.id)
    response = await client.post(
        INTAKE,
        json={**PAYLOAD, "description": "x" * (settings.LEADS_INTAKE_MAX_BODY_KB * 1024)},
        headers={"X-Lead-Key": key},
    )
    assert response.status_code == 413, response.text


@pytest.mark.asyncio
async def test_response_leaks_nothing(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """No id, no clinic, no "you are already our patient"."""
    key = await _mint_key(db_session, test_clinic.id)
    response = await client.post(
        INTAKE,
        json={**PAYLOAD, "phone": test_patient.phone, "email": test_patient.email},
        headers={"X-Lead-Key": key},
    )

    assert response.status_code == 201
    assert response.json() == {"data": {"received": True}, "message": None}
    body = response.text
    assert str(test_clinic.id) not in body
    assert test_patient.first_name not in body
    assert test_patient.phone not in body
    assert "recall" not in body.lower()


# ---------------------------------------------------------------------------
# Tenancy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_each_key_writes_to_its_own_clinic(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    other = await make_clinic(db_session, "Second Clinic")
    clinic_a_key = await _mint_key(db_session, test_clinic.id)
    clinic_b_key = await _mint_key(db_session, other.id)

    # The phone belongs to a patient of clinic A only.
    patient_a = await make_patient(db_session, test_clinic.id, phone="600111222")

    # Clinic B's key must not recall clinic A's patient: it is a new
    # person as far as B is concerned.
    b_response = await client.post(
        INTAKE, json={**PAYLOAD, "phone": "600111222"}, headers={"X-Lead-Key": clinic_b_key}
    )
    assert b_response.status_code == 201

    b_leads = list(
        (await db_session.execute(select(Lead).where(Lead.clinic_id == other.id))).scalars()
    )
    assert len(b_leads) == 1
    assert (
        await db_session.execute(select(Recall).where(Recall.patient_id == patient_a.id))
    ).scalars().all() == []

    # Clinic A's key recalls its own patient and writes no lead.
    a_response = await client.post(
        INTAKE, json={**PAYLOAD, "phone": "600111222"}, headers={"X-Lead-Key": clinic_a_key}
    )
    assert a_response.status_code == 201
    assert a_response.content == b_response.content
    assert (
        await db_session.execute(select(Lead).where(Lead.clinic_id == test_clinic.id))
    ).scalars().all() == []
    assert (
        len(
            (await db_session.execute(select(Recall).where(Recall.patient_id == patient_a.id)))
            .scalars()
            .all()
        )
        == 1
    )
    # Clinic B's own counter is untouched by clinic A's intake.
    b_usage = (
        await db_session.execute(select(LeadSettings).where(LeadSettings.clinic_id == other.id))
    ).scalar_one()
    assert b_usage.day_count == 1


# ---------------------------------------------------------------------------
# Daily cap (the clinic's own ceiling — D13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_cap_blocks_and_keeps_counting(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    key = await _mint_key(db_session, test_clinic.id)
    patched = await client.patch(
        "/api/v1/leads/settings", json={"daily_cap": 2}, headers=auth_headers
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["daily_cap"] == 2

    first = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": key})
    second = await client.post(
        INTAKE, json={**PAYLOAD, "phone": "699000002"}, headers={"X-Lead-Key": key}
    )
    blocked = await client.post(
        INTAKE, json={**PAYLOAD, "phone": "699000003"}, headers={"X-Lead-Key": key}
    )

    assert first.status_code == second.status_code == 201
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") == "3600"

    # Blocked attempts keep counting: the clinic sees the size of the
    # flood, not just that intake stopped.
    usage = (
        await db_session.execute(
            select(LeadSettings).where(LeadSettings.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    assert usage.day_count == 3

    # …and the count survives the request that was rejected. Read it back
    # through a *separate* connection: the test client shares one session
    # with the app (tests/conftest.py), which would happily show an
    # increment that a real deployment rolled back on the 429.
    durable = await _day_count_from_a_fresh_connection(test_clinic.id)
    assert durable == 3

    gauge = await client.get("/api/v1/leads/settings", headers=auth_headers)
    assert gauge.json()["data"]["day_count"] == 3

    # Only the two accepted ones became leads.
    leads = list(
        (await db_session.execute(select(Lead).where(Lead.clinic_id == test_clinic.id))).scalars()
    )
    assert len(leads) == 2


@pytest.mark.asyncio
async def test_unlimited_cap_never_trips(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    key = await _mint_key(db_session, test_clinic.id)
    await client.patch("/api/v1/leads/settings", json={"daily_cap": 0}, headers=auth_headers)

    for index in range(4):
        response = await client.post(
            INTAKE, json={**PAYLOAD, "phone": f"69900010{index}"}, headers={"X-Lead-Key": key}
        )
        assert response.status_code == 201
