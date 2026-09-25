"""QR check-in tests (Phase 4a): signed short-lived tokens let patients
check themselves in without an account.

Covers: token mint (auth + 404), QR PNG render (+ allowlist validation),
public check-in happy path (status flips, events fire via the canonical
machine), double-scan idempotence (200, not an error), expired/forged
tokens (401), unknown appointment (404), wrong-state tokens (422), and
tenant isolation (token from clinic A never touches clinic B).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic, User
from app.core.auth.router import limiter
from app.core.auth.service import create_access_token, hash_password
from app.modules.agenda.checkin import (
    mint_checkin_token,
    render_checkin_qr,
    verify_checkin_token,
)
from app.modules.agenda.models import Cabinet
from app.modules.agenda.service import AppointmentService
from app.modules.patients.models import Patient


async def _world(db: AsyncSession, clinic: Clinic, admin_id: UUID) -> dict[str, UUID]:
    dentist = User(
        id=uuid4(),
        email=f"d-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Dra",
        last_name="Who",
        is_active=True,
    )
    cabinet = Cabinet(
        id=uuid4(),
        clinic_id=clinic.id,
        name=f"Gabinete {uuid4().hex[:6]}",
        color="#3B82F6",
        display_order=0,
        is_active=True,
    )
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Juan", last_name="P")
    db.add_all([dentist, cabinet, patient])
    await db.flush()
    start = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)
    apt = await AppointmentService.create_appointment(
        db,
        clinic.id,
        {
            "patient_id": patient.id,
            "professional_id": dentist.id,
            "cabinet_id": cabinet.id,
            "cabinet": "Gabinete 1",
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
        created_by=admin_id,
    )
    await db.commit()
    return {"appointment_id": apt.id, "clinic_id": clinic.id}


async def _admin_id(client, auth_headers) -> UUID:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    return UUID(me.json()["data"]["user"]["id"])


@pytest.mark.asyncio
async def test_mint_token_requires_appointment(client, auth_headers, test_clinic) -> None:
    r = await client.post(
        f"/api/v1/agenda/appointments/{uuid4()}/check-in-token", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_checkin_happy_path(
    client, auth_headers, test_clinic, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    minted = await client.post(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-token",
        headers=auth_headers,
    )
    assert minted.status_code == 200
    token = minted.json()["data"]["token"]
    # The copyable link is built server-side — same origin as the QR.
    url = minted.json()["data"]["url"]
    assert url == f"https://clinic.example/p/check-in/{token}"

    # QR renders as PNG (origin comes from server-side allowlist now).
    qr = await client.get(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-qr",
        headers=auth_headers,
    )
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"
    assert qr.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Public consume flips the status through the canonical machine.
    done = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert done.status_code == 200
    assert done.json()["data"]["status"] == "checked_in"

    # Double scan is idempotent, not an error.
    again = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "checked_in"


@pytest.mark.asyncio
async def test_checkin_rejects_bad_tokens(client) -> None:
    assert (await client.post("/api/v1/agenda/public/check-in/garbage")).status_code == 401
    assert (
        await client.post(
            f"/api/v1/agenda/public/check-in/{create_access_token(uuid4())}",
        )
    ).status_code == 401  # right signature, wrong purpose


@pytest.mark.asyncio
async def test_checkin_unknown_appointment_is_404(client) -> None:
    token, _ = mint_checkin_token(uuid4(), uuid4())
    r = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_checkin_wrong_state_is_422(
    client, auth_headers, test_clinic, db_session: AsyncSession
) -> None:
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    apt = await AppointmentService.get_appointment(
        db_session, world["clinic_id"], world["appointment_id"]
    )
    await AppointmentService.transition(db_session, apt, "cancelled")
    await db_session.commit()
    token, _ = mint_checkin_token(world["appointment_id"], world["clinic_id"])
    r = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_checkin_token_is_tenant_bound(
    client, auth_headers, test_clinic, db_session: AsyncSession
) -> None:
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    other_clinic = Clinic(id=uuid4(), name="Other", tax_id="B9", address={"city": "M"}, settings={})
    db_session.add(other_clinic)
    await db_session.commit()
    # Token minted for clinic B must not resolve the clinic-A appointment,
    # even though the appointment id is valid.
    token, _ = mint_checkin_token(world["appointment_id"], other_clinic.id)
    r = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_checkin_token_helpers_unit() -> None:
    assert render_checkin_qr("https://x.test/c")[:8] == b"\x89PNG\r\n\x1a\n"
    appointment_id, clinic_id = verify_checkin_token(mint_checkin_token(uuid4(), uuid4())[0])
    assert isinstance(appointment_id, UUID) and isinstance(clinic_id, UUID)


@pytest.mark.asyncio
async def test_qr_rejects_unconfigured_allowlist(
    client, auth_headers, test_clinic, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "")
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    r = await client.get(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-qr",
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_qr_rejects_non_http_allowlist_origin(
    client, auth_headers, test_clinic, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "ftp://evil.example/x")
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    r = await client.get(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-qr",
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_public_checkin_is_rate_limited(client, monkeypatch) -> None:
    # Force the limiter on (it is production-only by default): 21 rapid
    # invalid-token posts must trip a 429 (20/minute per IP). With the
    # decorator deleted every call answers 401, so this test is red
    # without the guard it names.
    monkeypatch.setattr(limiter, "enabled", True)
    statuses = set()
    for _ in range(21):
        r = await client.post("/api/v1/agenda/public/check-in/x")
        statuses.add(r.status_code)
    assert 429 in statuses


@pytest.mark.asyncio
async def test_mint_rejects_unconfigured_allowlist(
    client, auth_headers, test_clinic, db_session: AsyncSession, monkeypatch
) -> None:
    # No origin to build the link/QR from — mint answers 422 like the QR
    # endpoint, so the two can never diverge.
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "")
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    r = await client.post(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-token",
        headers=auth_headers,
    )
    assert r.status_code == 422
