"""First-run setup: country presets + ``clinic.created`` seeding contract."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import EventType, event_bus
from app.modules.agenda.models import Cabinet
from app.modules.billing.models import InvoiceSeries
from app.modules.catalog.models import TreatmentCatalogItem, VatType
from app.modules.schedules.models import ClinicWeeklySchedule, ScheduleShift

_BASE = {
    "admin_first_name": "Ana",
    "admin_last_name": "Pérez",
    "admin_email": "ana@example.com",
    "admin_password": "SecurePass123",
    "clinic_name": "Clínica Sol",
    "clinic_tax_id": "B12345678",
}


async def _count(db: AsyncSession, model, clinic_id) -> int:
    return await db.scalar(
        select(func.count()).select_from(model).where(model.clinic_id == clinic_id)
    )


@pytest.mark.asyncio
async def test_setup_presets_public(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/setup/presets")
    assert r.status_code == 200
    data = r.json()["data"]
    es = next(c for c in data["countries"] if c["code"] == "ES")
    assert es["currency"] == "EUR" and es["vat_preset"] == "es"
    assert es["suggested_modules"] == ["verifactu"]
    assert data["fallback"]["vat_preset"] == "generic"


@pytest.mark.asyncio
async def test_setup_es_applies_preset_and_seeds(client: AsyncClient, db_session: AsyncSession):
    r = await client.post("/api/v1/auth/setup", json={**_BASE, "country": "es"})
    assert r.status_code == 201, r.text

    clinic = (await db_session.execute(select(Clinic))).scalar_one()
    assert clinic.timezone == "Europe/Madrid"
    assert clinic.currency == "EUR"
    assert clinic.settings["country"] == "ES"
    assert clinic.settings["communication_language"] == "es"
    assert clinic.address == {"country": "ES"}

    # clinic.created → modules seeded their defaults
    assert await _count(db_session, VatType, clinic.id) == 3
    assert await _count(db_session, TreatmentCatalogItem, clinic.id) > 100
    assert await _count(db_session, Cabinet, clinic.id) == 1
    series = (
        (
            await db_session.execute(
                select(InvoiceSeries).where(InvoiceSeries.clinic_id == clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert {s.prefix for s in series} == {"FAC", "RECT"}
    assert all(s.is_default for s in series)
    weekly = (
        await db_session.execute(
            select(ClinicWeeklySchedule).where(ClinicWeeklySchedule.clinic_id == clinic.id)
        )
    ).scalar_one()
    shifts = (
        (
            await db_session.execute(
                select(ScheduleShift).where(ScheduleShift.clinic_weekly_id == weekly.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(shifts) == 10  # Mon–Fri × split shift
    assert {s.weekday for s in shifts} == {0, 1, 2, 3, 4}

    # a priced item — ES keeps reference prices
    priced = await db_session.scalar(
        select(func.count())
        .select_from(TreatmentCatalogItem)
        .where(TreatmentCatalogItem.clinic_id == clinic.id, TreatmentCatalogItem.default_price > 0)
    )
    assert priced > 0


@pytest.mark.asyncio
async def test_setup_accepts_address_and_solo_professional(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """#205: the wizard can complete the clinic-info and team onboarding
    steps directly — street lands in the address, the admin membership
    is flagged professional."""
    from app.core.auth.models import ClinicMembership

    r = await client.post(
        "/api/v1/auth/setup",
        json={
            **_BASE,
            "country": "es",
            "admin_is_professional": True,
            "clinic_street": "Calle Mayor 1",
            "clinic_postal_code": "28001",
            "clinic_city": "Madrid",
        },
    )
    assert r.status_code == 201, r.text

    clinic = (await db_session.execute(select(Clinic))).scalar_one()
    assert clinic.address == {
        "country": "ES",
        "street": "Calle Mayor 1",
        "city": "Madrid",
        "postal_code": "28001",
    }
    membership = (await db_session.execute(select(ClinicMembership))).scalar_one()
    assert membership.is_professional is True


@pytest.mark.asyncio
async def test_setup_without_new_fields_keeps_legacy_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pre-existing callers change nothing: no address keys beyond the
    country, membership not professional."""
    from app.core.auth.models import ClinicMembership

    r = await client.post("/api/v1/auth/setup", json={**_BASE, "country": "es"})
    assert r.status_code == 201, r.text

    clinic = (await db_session.execute(select(Clinic))).scalar_one()
    assert clinic.address == {"country": "ES"}
    membership = (await db_session.execute(select(ClinicMembership))).scalar_one()
    assert membership.is_professional is False


@pytest.mark.asyncio
async def test_setup_es_rejects_bad_tax_id_format(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/setup", json={**_BASE, "country": "ES", "clinic_tax_id": "1234"}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_setup_unknown_country_generic_no_prices(client: AsyncClient, db_session):
    r = await client.post(
        "/api/v1/auth/setup",
        json={**_BASE, "country": "MX", "clinic_tax_id": "ABC010203XYZ"},
    )
    assert r.status_code == 201, r.text
    clinic = (await db_session.execute(select(Clinic))).scalar_one()
    assert clinic.currency == "MXN"
    assert clinic.timezone == "America/Mexico_City"
    assert clinic.settings["communication_language"] == "es"
    assert await _count(db_session, VatType, clinic.id) == 1  # generic → exempt only
    priced = await db_session.scalar(
        select(func.count())
        .select_from(TreatmentCatalogItem)
        .where(TreatmentCatalogItem.clinic_id == clinic.id, TreatmentCatalogItem.default_price > 0)
    )
    assert priced == 0
    weekly = (
        await db_session.execute(
            select(ClinicWeeklySchedule).where(ClinicWeeklySchedule.clinic_id == clinic.id)
        )
    ).scalar_one()
    n = await db_session.scalar(
        select(func.count())
        .select_from(ScheduleShift)
        .where(ScheduleShift.clinic_weekly_id == weekly.id)
    )
    assert n == 5  # Mon–Fri single shift


@pytest.mark.asyncio
async def test_setup_without_country_keeps_legacy_defaults(client: AsyncClient, db_session):
    r = await client.post("/api/v1/auth/setup", json=_BASE)
    assert r.status_code == 201
    clinic = (await db_session.execute(select(Clinic))).scalar_one()
    assert clinic.timezone == "Europe/Madrid" and clinic.currency == "EUR"
    assert "country" not in clinic.settings


@pytest.mark.asyncio
async def test_clinic_created_handlers_are_idempotent(client: AsyncClient, db_session):
    r = await client.post("/api/v1/auth/setup", json={**_BASE, "country": "ES"})
    assert r.status_code == 201
    clinic_id = (await db_session.execute(select(Clinic.id))).scalar_one()
    before = (
        await _count(db_session, VatType, clinic_id),
        await _count(db_session, TreatmentCatalogItem, clinic_id),
        await _count(db_session, Cabinet, clinic_id),
        await _count(db_session, InvoiceSeries, clinic_id),
        await _count(db_session, ClinicWeeklySchedule, clinic_id),
    )
    await event_bus.publish(
        EventType.CLINIC_CREATED,
        {
            "clinic_id": str(clinic_id),
            "country": "ES",
            "currency": "EUR",
            "language": "es",
            "vat_preset": "es",
            "source": "test",
        },
    )
    after = (
        await _count(db_session, VatType, clinic_id),
        await _count(db_session, TreatmentCatalogItem, clinic_id),
        await _count(db_session, Cabinet, clinic_id),
        await _count(db_session, InvoiceSeries, clinic_id),
        await _count(db_session, ClinicWeeklySchedule, clinic_id),
    )
    assert before == after


@pytest.mark.asyncio
async def test_onboarding_state_patch(client: AsyncClient, auth_headers: dict, test_clinic) -> None:
    r = await client.patch(
        "/api/v1/auth/clinic/settings/onboarding",
        json={"skip": ["smtp", "verifactu"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert set(r.json()["data"]["skipped"]) == {"smtp", "verifactu"}
    assert r.json()["data"]["dismissed_at"] is None

    r = await client.patch(
        "/api/v1/auth/clinic/settings/onboarding",
        json={"unskip": ["smtp"], "dismissed": True},
        headers=auth_headers,
    )
    data = r.json()["data"]
    assert set(data["skipped"]) == {"verifactu"} and data["dismissed_at"]

    # state travels with the clinic metadata
    r = await client.get("/api/v1/auth/clinics", headers=auth_headers)
    assert "verifactu" in r.json()["data"][0]["settings"]["onboarding"]["skipped"]

    r = await client.patch(
        "/api/v1/auth/clinic/settings/onboarding", json={"reset": True}, headers=auth_headers
    )
    assert r.json()["data"] == {"dismissed_at": None, "completed_at": None, "skipped": {}}


@pytest.mark.asyncio
async def test_onboarding_state_requires_admin(
    client: AsyncClient, auth_headers: dict, db_session, test_clinic
):
    from app.core.auth.models import ClinicMembership

    membership = (await db_session.execute(select(ClinicMembership))).scalar_one()
    membership.role = "receptionist"
    await db_session.commit()
    r = await client.patch(
        "/api/v1/auth/clinic/settings/onboarding", json={"dismissed": True}, headers=auth_headers
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Invite links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_link_flow(client: AsyncClient, auth_headers: dict, test_clinic) -> None:
    # Create a professional without a password
    r = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "dentist@example.com",
            "first_name": "Dana",
            "last_name": "Dent",
            "role": "dentist",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["data"]["id"]

    # Cannot log in yet
    r = await client.post(
        "/api/v1/auth/login", data={"username": "dentist@example.com", "password": "anything1"}
    )
    assert r.status_code == 401

    # Admin mints the link
    r = await client.post(f"/api/v1/auth/users/{user_id}/invite-link", headers=auth_headers)
    assert r.status_code == 200, r.text
    token = r.json()["data"]["token"]

    # The invite token is not a bearer token
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401

    # Weak password rejected
    r = await client.post("/api/v1/auth/set-password", json={"token": token, "password": "short"})
    assert r.status_code == 422

    # Consume → tokens back
    r = await client.post(
        "/api/v1/auth/set-password", json={"token": token, "password": "NewPassword123"}
    )
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["data"]["user"]["email"] == "dentist@example.com"

    # Single use
    r = await client.post(
        "/api/v1/auth/set-password", json={"token": token, "password": "OtherPass123"}
    )
    assert r.status_code == 400

    # New password works
    r = await client.post(
        "/api/v1/auth/login", data={"username": "dentist@example.com", "password": "NewPassword123"}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_invite_link_scoped_to_clinic_and_admin(
    client: AsyncClient, auth_headers: dict, test_clinic, db_session
) -> None:
    from uuid import uuid4

    r = await client.post(f"/api/v1/auth/users/{uuid4()}/invite-link", headers=auth_headers)
    assert r.status_code == 404

    from app.core.auth.models import ClinicMembership

    membership = (await db_session.execute(select(ClinicMembership))).scalar_one()
    membership.role = "dentist"
    await db_session.commit()
    r = await client.post(
        f"/api/v1/auth/users/{membership.user_id}/invite-link", headers=auth_headers
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_set_password_rejects_garbage_token(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/set-password", json={"token": "not-a-jwt", "password": "NewPassword123"}
    )
    assert r.status_code == 400
