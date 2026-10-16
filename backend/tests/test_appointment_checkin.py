"""QR check-in tests (Phase 4a): signed short-lived tokens let patients
check themselves in without an account.

Covers: token mint (auth + 404), QR PNG render (+ allowlist validation),
public check-in happy path (status flips, events fire via the canonical
machine), double-scan idempotence (200, not an error), expired/forged
tokens (401), unknown appointment (404), wrong-state tokens (422), and
tenant isolation (token from clinic A never touches clinic B).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic, User
from app.core.auth.router import limiter
from app.core.auth.service import create_access_token, hash_password
from app.modules.agenda.checkin import (
    _checkin_secret,
    mint_checkin_token,
    render_checkin_qr,
    verify_checkin_token,
)
from app.modules.agenda.models import Cabinet
from app.modules.agenda.service import AppointmentService
from app.modules.patients.models import Patient


async def _world(db: AsyncSession, clinic: Clinic, admin_id: UUID) -> dict[str, UUID]:
    # Near-future start: inside the ADR 0037 check-in window (opens two
    # hours before start), so the happy path exercises the window pass.
    return await _world_at(db, clinic, admin_id, datetime.now(UTC) + timedelta(minutes=30))


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


def test_checkin_secret_hard_required_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """No key in production refuses to sign; dev still falls back (#538)."""
    monkeypatch.setattr(settings, "AGENDA_PUBLIC_SECRET_KEY", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        _checkin_secret()
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert _checkin_secret() == settings.SECRET_KEY
    monkeypatch.setattr(settings, "AGENDA_PUBLIC_SECRET_KEY", " " * 32)
    assert _checkin_secret() == settings.SECRET_KEY
    monkeypatch.setattr(settings, "AGENDA_PUBLIC_SECRET_KEY", "a" * 32 + " ")
    assert _checkin_secret() == "a" * 32


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
    appointment_id, clinic_id, source = verify_checkin_token(
        mint_checkin_token(uuid4(), uuid4())[0]
    )
    assert isinstance(appointment_id, UUID) and isinstance(clinic_id, UUID)
    assert source == "counter"  # mint default preserves the QR-at-counter flow


def test_checkin_source_round_trip() -> None:
    """ADR 0037: counter/reminder/kiosk survive; missing/garbage fail safe to reminder."""
    from jose import jwt as _jwt

    aid, cid = uuid4(), uuid4()
    assert verify_checkin_token(mint_checkin_token(aid, cid, source="counter")[0])[2] == "counter"
    assert verify_checkin_token(mint_checkin_token(aid, cid, source="reminder")[0])[2] == "reminder"
    assert verify_checkin_token(mint_checkin_token(aid, cid, source="kiosk")[0])[2] == "kiosk"

    for payload in (
        {"type": "checkin", "appointment_id": str(aid), "clinic_id": str(cid)},
        {
            "type": "checkin",
            "appointment_id": str(aid),
            "clinic_id": str(cid),
            "source": "warp-drive",
        },
    ):
        token = _jwt.encode(payload, _checkin_secret(), algorithm=settings.ALGORITHM)
        assert verify_checkin_token(token)[2] == "reminder"


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


async def _world_at(
    db_session: AsyncSession, clinic: Clinic, admin_id: UUID, start: datetime
) -> dict[str, UUID]:
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
    db_session.add_all([dentist, cabinet, patient])
    await db_session.flush()
    apt = await AppointmentService.create_appointment(
        db_session,
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
    await db_session.commit()
    return {"appointment_id": apt.id, "clinic_id": clinic.id}


@pytest.mark.asyncio
async def test_checkin_too_early_is_422_with_code(
    client, auth_headers, test_clinic, db_session: AsyncSession
) -> None:
    """ADR 0037: outside the window the page messages precisely (code + local start)."""
    world = await _world_at(
        db_session,
        test_clinic,
        await _admin_id(client, auth_headers),
        datetime.now(UTC) + timedelta(hours=5),
    )
    token, _ = mint_checkin_token(world["appointment_id"], world["clinic_id"])
    r = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert r.status_code == 422
    detail = r.json()["message"]
    assert detail.startswith("too_early:")
    assert re.fullmatch(r"too_early:\d{2}:\d{2}", detail)


@pytest.mark.asyncio
async def test_checkin_window_closed_is_422_with_code(
    client, auth_headers, test_clinic, db_session: AsyncSession
) -> None:
    world = await _world_at(
        db_session,
        test_clinic,
        await _admin_id(client, auth_headers),
        datetime.now(UTC) - timedelta(hours=3),
    )
    token, _ = mint_checkin_token(world["appointment_id"], world["clinic_id"])
    r = await client.post(f"/api/v1/agenda/public/check-in/{token}")
    assert r.status_code == 422
    assert r.json()["message"] == "window_closed"


@pytest.mark.asyncio
async def test_mint_source_param_defaults_to_counter(
    client, auth_headers, test_clinic, db_session: AsyncSession, monkeypatch
) -> None:
    """Staff QR flow keeps auto-submit; mailed links mint reminder explicitly."""
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")
    world = await _world(db_session, test_clinic, await _admin_id(client, auth_headers))
    default = await client.post(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-token",
        headers=auth_headers,
    )
    assert default.status_code == 200
    _, _, source = verify_checkin_token(default.json()["data"]["token"])
    assert source == "counter"
    reminder = await client.post(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-token?source=reminder",
        headers=auth_headers,
    )
    assert reminder.status_code == 200
    _, _, source = verify_checkin_token(reminder.json()["data"]["token"])
    assert source == "reminder"
    bogus = await client.post(
        f"/api/v1/agenda/appointments/{world['appointment_id']}/check-in-token?source=warp",
        headers=auth_headers,
    )
    assert bogus.status_code == 422


def test_reminder_checkin_url_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sweep helper mints a day-valid reminder link; degrades to None with no origin."""
    from types import SimpleNamespace

    from app.modules.notifications.tasks import _reminder_checkin_url

    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")
    apt = SimpleNamespace(
        id=uuid4(),
        clinic_id=uuid4(),
        start_time=datetime.now(UTC) + timedelta(hours=5),
    )
    clinic = SimpleNamespace(timezone="Europe/Madrid")
    url = _reminder_checkin_url(apt, clinic)
    assert url is not None and url.startswith("https://clinic.example/p/check-in/")
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "")
    assert _reminder_checkin_url(apt, clinic) is None


def test_reminder_link_mint_failure_is_error_not_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A permanently broken minter must not hide behind a WARNING forever (#667)."""
    import logging
    from types import SimpleNamespace

    import app.modules.agenda.checkin as _checkin
    import app.modules.notifications.tasks as _tasks

    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")
    monkeypatch.setattr(
        _checkin,
        "mint_checkin_token",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("bad key")),
    )
    apt = SimpleNamespace(
        id=uuid4(),
        clinic_id=uuid4(),
        start_time=datetime.now(UTC) + timedelta(hours=5),
    )
    clinic = SimpleNamespace(timezone="Europe/Madrid")
    with caplog.at_level(logging.ERROR, logger="app.modules.notifications.tasks"):
        assert _tasks._reminder_checkin_url(apt, clinic) is None
    assert any(r.levelno >= logging.ERROR for r in caplog.records)
