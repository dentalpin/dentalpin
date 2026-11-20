from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest
from booking_helpers import clinic_user, configure, dispatch, professional, proof_for
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.auth.models import ClinicMembership, User
from app.modules.agenda.models import Appointment
from app.modules.notifications.models import CommunicationMessage
from app.modules.online_booking.exceptions import BookingConflictError
from app.modules.online_booking.models import BookingRequest, BookingSettings
from app.modules.online_booking.service import digest, reserve


@pytest.mark.asyncio
async def test_request_confirm_accept_and_conflict(
    client, db_session, auth_headers, test_clinic, open_hours, delivery
):
    from app.core.auth.service import hash_password

    professional = User(
        id=uuid4(),
        email=f"{uuid4()}@example.invalid",
        password_hash=hash_password("Synthetic123!"),
        first_name="Test",
        last_name="Dentist",
        is_active=True,
    )
    db_session.add(professional)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=professional.id,
            clinic_id=test_clinic.id,
            role="dentist",
            is_professional=True,
        )
    )
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=professional.id,
            public_url="https://example.invalid/book",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    await db_session.commit()
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    start = datetime.combine(tomorrow, time(10), UTC)
    url = f"/api/v1/online_booking/public/{test_clinic.id}"
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    settings = await client.get("/api/v1/online_booking/settings", headers=headers)
    assert settings.status_code == 200
    config = {
        **settings.json()["data"],
        "title_es": "Reserva sintética",
        "accent_color": "#123456",
    }
    saved = await client.put("/api/v1/online_booking/settings", headers=headers, json=config)
    assert saved.status_code == 200, saved.text
    public = await client.get(f"{url}/config")
    assert public.json()["data"]["branding"]["title_es"] == "Reserva sintética"
    assert public.json()["data"]["branding"]["logo_url"] is None
    availability = await client.get(f"{url}/availability", params={"day": tomorrow.isoformat()})
    assert availability.status_code == 200
    assert start.isoformat() in availability.json()["data"]["starts"]
    week = await client.get(
        f"{url}/availability", params={"from_day": tomorrow.isoformat(), "days": 7}
    )
    assert week.status_code == 200
    assert start.isoformat() in week.json()["data"]["days"][0]["starts"]
    assert (
        await client.get(
            f"{url}/availability", params={"from_day": tomorrow.isoformat(), "days": 32}
        )
    ).status_code == 422
    from altcha import Challenge, Payload, solve_challenge

    challenge_response = await client.get(f"{url}/challenge")
    assert challenge_response.status_code == 200
    assert challenge_response.headers["cache-control"] == "no-store"
    issued = Challenge.from_dict(challenge_response.json())
    solution = solve_challenge(issued, timeout=20)
    assert solution is not None
    body = {
        "start_time": start.isoformat(),
        "contact_name": "Synthetic",
        "contact_email": "test@example.com",
        "contact_phone": "+34600123456",
        "reason": "checkup",
        "altcha": Payload(issued, solution).to_base64(),
    }
    first = await client.post(f"{url}/requests", json=body)
    assert first.status_code == 201, first.text
    duplicate = await client.post(f"{url}/requests", json=body)
    assert duplicate.status_code == 409
    await db_session.commit()
    assert delivery == []
    assert await dispatch(db_session) == 1
    token = delivery[0].body_text.split("#token=")[1].split()[0]
    assert delivery[0].to_email == "test@example.com"
    assert delivery[0].subject.startswith("Confirma tu solicitud de cita en ")
    assert "<a href=" in delivery[0].body_html and token in delivery[0].body_html
    assert "{{" not in delivery[0].body_html + delivery[0].body_text
    assert "se pondrá en contacto contigo" in delivery[0].body_text
    from zoneinfo import ZoneInfo

    local = start.astimezone(ZoneInfo("Europe/Madrid"))
    assert local.strftime("%d/%m/%Y") in delivery[0].body_text
    assert local.strftime("%H:%M") in delivery[0].body_text
    response = await client.post(f"{url}/confirm", json={"token": token})
    assert response.status_code == 200
    assert response.json()["data"]["start_time"] == start.isoformat()
    assert (await client.post(f"{url}/confirm", json={"token": token})).status_code == 410
    item = await db_session.scalar(
        select(BookingRequest).where(BookingRequest.clinic_id == test_clinic.id)
    )
    busy = Appointment(
        clinic_id=test_clinic.id,
        professional_id=professional.id,
        start_time=start + timedelta(minutes=15),
        end_time=start + timedelta(minutes=45),
        status="scheduled",
    )
    db_session.add(busy)
    await db_session.flush()
    result = await client.post(
        f"/api/v1/online_booking/requests/{item.id}/accept",
        headers=headers,
        json={
            "first_name": "Synthetic",
            "last_name": "Person",
            "professional_id": str(professional.id),
            "duration_minutes": 30,
        },
    )
    assert result.status_code == 409, result.text
    assert item.status == "confirmed"
    await db_session.delete(busy)
    await db_session.flush()
    accepted = await client.post(
        f"/api/v1/online_booking/requests/{item.id}/accept",
        headers=headers,
        json={
            "first_name": "Synthetic",
            "last_name": "Person",
            "professional_id": str(professional.id),
            "duration_minutes": 30,
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert item.status == "accepted" and item.patient_id and item.appointment_id
    repeat = await client.post(
        f"/api/v1/online_booking/requests/{item.id}/accept",
        headers=headers,
        json={
            "first_name": "Synthetic",
            "last_name": "Person",
            "professional_id": str(professional.id),
            "duration_minutes": 30,
        },
    )
    assert repeat.status_code == 409


@pytest.mark.asyncio
async def test_simultaneous_reservations_serialize(db_session, test_clinic, open_hours):
    from app.config import settings

    professional_id = await clinic_user(db_session, test_clinic.id)
    config = BookingSettings(
        clinic_id=test_clinic.id,
        enabled=True,
        professional_id=professional_id,
        slot_minutes=30,
        window_days=30,
        min_notice_minutes=0,
    )
    db_session.add(config)
    await db_session.commit()
    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(10), UTC)
    engine = create_async_engine(settings.DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def attempt():
        async with maker() as db:
            cfg = await db.get(BookingSettings, test_clinic.id)
            row = BookingRequest(
                clinic_id=test_clinic.id,
                professional_id=professional_id,
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status="pending_confirmation",
                reason="checkup",
                confirmation_deadline=datetime.now(UTC) + timedelta(minutes=10),
            )
            try:
                await reserve(db, test_clinic.id, cfg, row, datetime.now(UTC))
                await db.commit()
                return "created"
            except BookingConflictError:
                await db.rollback()
                return "conflict"

    try:
        assert sorted(await asyncio.gather(attempt(), attempt())) == ["conflict", "created"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_simultaneous_http_requests(client, db_session, test_clinic, open_hours, delivery):
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient

    from app.config import settings
    from app.database import get_db
    from app.main import app

    professional_id = await db_session.scalar(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
    )
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=professional_id,
            public_url="https://example.invalid/book",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    await db_session.commit()
    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(12), UTC)
    engine = create_async_engine(settings.DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    original = app.dependency_overrides[get_db]

    async def separate_sessions() -> AsyncGenerator:
        async with maker() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = separate_sessions
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as parallel:
            url = f"/api/v1/online_booking/public/{test_clinic.id}/requests"
            body = {
                "start_time": start.isoformat(),
                "contact_name": "Synthetic",
                "contact_email": "parallel@example.com",
                "contact_phone": "+34600123456",
                "reason": "checkup",
                "altcha": proof_for(test_clinic.id),
            }
            responses = await asyncio.gather(
                parallel.post(url, json=body),
                parallel.post(url, json={**body, "altcha": proof_for(test_clinic.id)}),
            )
            assert sorted(r.status_code for r in responses) == [201, 409], [
                r.text for r in responses
            ]
    finally:
        app.dependency_overrides[get_db] = original
        await engine.dispose()


@pytest.mark.asyncio
async def test_cleanup_expiry_and_contact_retention(db_session, test_clinic):
    from app.modules.online_booking.tasks import cleanup

    now = datetime.now(UTC)
    professional_id = await clinic_user(db_session, test_clinic.id)

    def item(status, start_delta, decided_delta=None):
        return BookingRequest(
            id=uuid4(),
            clinic_id=test_clinic.id,
            professional_id=professional_id,
            status=status,
            reason="checkup",
            start_time=now + start_delta,
            end_time=now + start_delta + timedelta(minutes=30),
            confirmation_deadline=now - timedelta(minutes=1),
            decided_at=now + decided_delta if decided_delta else None,
            contact_name="Synthetic",
            contact_email="synthetic@example.invalid",
            contact_phone="12345",
            token_hash=uuid4().hex,
        )

    expired = item("pending_confirmation", timedelta(days=1))
    finished = item("confirmed", -timedelta(hours=1))
    rejected = item("rejected", -timedelta(days=32), -timedelta(days=31))
    accepted = item("accepted", -timedelta(days=100), -timedelta(days=91))
    recent = item("accepted", -timedelta(days=2), -timedelta(days=1))
    db_session.add_all([expired, finished, rejected, accepted, recent])
    await db_session.commit()
    ids = [row.id for row in (expired, finished, rejected, accepted, recent)]
    await cleanup()
    db_session.expire_all()
    a, b, c, d, e = [await db_session.get(BookingRequest, item_id) for item_id in ids]
    assert a.status == "expired" and a.token_hash is None
    assert b.status == "expired" and b.token_hash is None
    assert c is None
    assert d.contact_name is None and d.contact_email is None and d.contact_phone is None
    assert e.contact_name == "Synthetic"


@pytest.mark.asyncio
async def test_rejection_sends_message_and_releases_hold(
    client, db_session, auth_headers, test_clinic, open_hours, delivery
):
    from app.core.auth.service import hash_password

    professional = User(
        id=uuid4(),
        email=f"{uuid4()}@example.invalid",
        password_hash=hash_password("Synthetic123!"),
        first_name="Test",
        last_name="Dentist",
        is_active=True,
    )
    db_session.add(professional)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=professional.id,
            clinic_id=test_clinic.id,
            role="dentist",
            is_professional=True,
        )
    )
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=professional.id,
            public_url="https://example.invalid/book",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    await db_session.commit()
    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(15), UTC)
    base = f"/api/v1/online_booking/public/{test_clinic.id}"
    body = {
        "start_time": start.isoformat(),
        "contact_name": "Synthetic",
        "contact_email": "reject@example.com",
        "contact_phone": "+34600123456",
        "reason": "checkup",
        "altcha": proof_for(test_clinic.id),
    }
    response = await client.post(f"{base}/requests", json=body)
    assert response.status_code == 201, response.text
    row = await db_session.scalar(
        select(BookingRequest).where(BookingRequest.clinic_id == test_clinic.id)
    )
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    response = await client.post(
        f"/api/v1/online_booking/requests/{row.id}/reject",
        json={"message": "Please call us"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert row.status == "rejected" and row.token_hash is None
    # Confirmation and rejection both go through the gateway outbox.
    assert await dispatch(db_session) == 2
    rejection = delivery[-1]
    assert rejection.to_email == "reject@example.com"
    assert rejection.subject.startswith("Novedades sobre tu solicitud de cita en ")
    assert "Please call us" in rejection.body_text and "Please call us" in rejection.body_html
    body["altcha"] = proof_for(test_clinic.id)
    assert (await client.post(f"{base}/requests", json=body)).status_code == 201


@pytest.mark.asyncio
async def test_shared_contact_limit_is_atomic_and_pseudonymous(db_session, test_clinic):
    from fastapi import HTTPException

    from app.modules.online_booking.models import BookingRateLimit
    from app.modules.online_booking.rate_limit import consume_rate

    identity = f"{test_clinic.id}:person@example.com"
    results = await asyncio.gather(
        *(consume_rate("test-contact", identity, 3) for _ in range(4)), return_exceptions=True
    )
    assert sum(result is None for result in results) == 3
    assert (
        sum(isinstance(result, HTTPException) and result.status_code == 429 for result in results)
        == 1
    )
    db_session.expire_all()
    rows = (await db_session.scalars(select(BookingRateLimit))).all()
    assert len(rows) == 1 and rows[0].attempts == 4 and identity not in rows[0].key


@pytest.mark.asyncio
async def test_public_api_is_disabled_by_default_and_rejects_clinical_fields(client, test_clinic):
    url = f"/api/v1/online_booking/public/{test_clinic.id}"
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    assert (
        await client.get(f"{url}/availability", params={"day": tomorrow.isoformat()})
    ).status_code == 404
    response = await client.post(
        f"{url}/requests",
        json={
            "start_time": datetime.combine(tomorrow, time(10), UTC).isoformat(),
            "contact_name": "Synthetic",
            "contact_email": "test@example.com",
            "reason": "checkup",
            "clinical_notes": "not accepted",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_staff_routes_require_login(client):
    assert (await client.get("/api/v1/online_booking/requests")).status_code == 401
    assert (await client.get("/api/v1/online_booking/settings")).status_code == 401
    assert (
        await client.put(
            "/api/v1/online_booking/settings/logo", json={"filename": "x.png", "data": "eA=="}
        )
    ).status_code == 401
    assert (await client.delete("/api/v1/online_booking/settings/logo")).status_code == 401


@pytest.mark.asyncio
async def test_simultaneous_accept_creates_only_one_appointment(
    client, db_session, auth_headers, test_clinic
):
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient

    from app.config import settings
    from app.core.auth.service import hash_password
    from app.database import get_db
    from app.main import app
    from app.modules.patient_timeline.models import PatientTimeline
    from app.modules.patients.models import Patient

    professional = User(
        id=uuid4(),
        email=f"{uuid4()}@example.invalid",
        password_hash=hash_password("Synthetic123!"),
        first_name="Test",
        last_name="Dentist",
        is_active=True,
    )
    db_session.add(professional)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=professional.id,
            clinic_id=test_clinic.id,
            role="dentist",
            is_professional=True,
        )
    )
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=professional.id,
            public_url="https://example.invalid/book",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    start = datetime.now(UTC) + timedelta(days=1)
    row = BookingRequest(
        id=uuid4(),
        clinic_id=test_clinic.id,
        professional_id=professional.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="confirmed",
        reason="checkup",
        confirmation_deadline=datetime.now(UTC),
        contact_email="test@example.com",
    )
    db_session.add(row)
    clinic_id = test_clinic.id
    await db_session.commit()
    engine = create_async_engine(settings.DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    original = app.dependency_overrides[get_db]

    async def separate_sessions() -> AsyncGenerator:
        async with maker() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = separate_sessions
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as parallel:
            url = f"/api/v1/online_booking/requests/{row.id}/accept"
            headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
            payload = {
                "first_name": "Synthetic",
                "last_name": "Person",
                "professional_id": str(professional.id),
                "duration_minutes": 30,
            }
            responses = await asyncio.gather(
                parallel.post(url, json=payload, headers=headers),
                parallel.post(url, json=payload, headers=headers),
            )
            assert sorted(r.status_code for r in responses) == [200, 409], [
                r.text for r in responses
            ]
        db_session.expire_all()
        assert (
            len(
                (
                    await db_session.scalars(
                        select(Appointment).where(Appointment.clinic_id == clinic_id)
                    )
                ).all()
            )
            == 1
        )
        assert (
            len(
                (
                    await db_session.scalars(select(Patient).where(Patient.clinic_id == clinic_id))
                ).all()
            )
            == 1
        )
        entries = (
            await db_session.scalars(
                select(PatientTimeline).where(
                    PatientTimeline.clinic_id == clinic_id,
                    PatientTimeline.event_type == "appointment.scheduled",
                )
            )
        ).all()
        assert len(entries) == 1
    finally:
        app.dependency_overrides[get_db] = original
        await engine.dispose()


@pytest.mark.asyncio
async def test_appointment_timeline_is_transactional_and_savepoint_isolated(
    db_session, test_clinic
):
    from app.modules.patient_timeline.events import on_appointment_scheduled
    from app.modules.patient_timeline.models import PatientTimeline
    from app.modules.patients.models import Patient

    patient = Patient(
        id=uuid4(), clinic_id=test_clinic.id, first_name="Synthetic", last_name="Patient"
    )
    patient_id = patient.id
    db_session.add(patient)
    await db_session.flush()
    payload = {
        "clinic_id": str(test_clinic.id),
        "patient_id": str(patient.id),
        "appointment_id": str(uuid4()),
    }
    await on_appointment_scheduled(payload, db=db_session)
    assert await db_session.scalar(
        select(PatientTimeline.id).where(PatientTimeline.patient_id == patient.id)
    )
    bad = {**payload, "patient_id": str(uuid4())}
    await on_appointment_scheduled(bad, db=db_session)
    assert await db_session.scalar(select(Patient.id).where(Patient.id == patient.id)) == patient.id
    await db_session.rollback()
    assert await db_session.scalar(select(Patient.id).where(Patient.id == patient_id)) is None


@pytest.mark.asyncio
async def test_staff_list_paginates_and_excludes_expired_requests(
    client, db_session, auth_headers, test_clinic, delivery
):
    now = datetime.now(UTC)
    professional_id = await clinic_user(db_session, test_clinic.id)

    def request(status, start, deadline):
        return BookingRequest(
            id=uuid4(),
            clinic_id=test_clinic.id,
            professional_id=professional_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=status,
            reason="checkup",
            confirmation_deadline=deadline,
            contact_email="test@example.com",
        )

    for index in range(51):
        db_session.add(
            request(
                "confirmed", now + timedelta(days=1, minutes=index), now + timedelta(minutes=10)
            )
        )
    stale_pending = request(
        "pending_confirmation", now + timedelta(days=1), now - timedelta(seconds=1)
    )
    stale_confirmed = request("confirmed", now - timedelta(minutes=1), now - timedelta(minutes=10))
    db_session.add_all([stale_pending, stale_confirmed])
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    first = await client.get("/api/v1/online_booking/requests?page=1", headers=headers)
    second = await client.get("/api/v1/online_booking/requests?page=2", headers=headers)
    assert first.status_code == second.status_code == 200
    assert len(first.json()["data"]) == 50 and first.json()["total"] == 51
    assert first.json()["page"] == 1 and first.json()["page_size"] == 50
    assert len(second.json()["data"]) == 1 and second.json()["page"] == 2
    for row in (stale_pending, stale_confirmed):
        result = await client.post(
            f"/api/v1/online_booking/requests/{row.id}/reject",
            headers=headers,
            json={"message": "Synthetic"},
        )
        assert result.status_code == 409
    assert await dispatch(db_session) == 0
    assert delivery == []


@pytest.mark.asyncio
async def test_rolled_back_request_queues_no_email(db_session, test_clinic, open_hours, delivery):
    """The gateway enqueues inside the caller's transaction: no commit, no mail."""
    professional_id = await clinic_user(db_session, test_clinic.id)
    config = BookingSettings(
        clinic_id=test_clinic.id,
        enabled=True,
        professional_id=professional_id,
        public_url="https://example.invalid/book",
        slot_minutes=30,
        window_days=30,
        min_notice_minutes=0,
    )
    db_session.add(config)
    await db_session.commit()
    from app.modules.online_booking.schemas import RequestInput
    from app.modules.online_booking.service import BookingService

    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(10), UTC)
    await BookingService.create_request(
        db_session,
        test_clinic.id,
        RequestInput(
            start_time=start,
            contact_name="Synthetic",
            contact_email="rollback@example.com",
            contact_phone="+34600000000",
            reason="checkup",
            altcha="verified-by-the-route",
        ),
    )
    assert await db_session.scalar(
        select(CommunicationMessage.id).where(
            CommunicationMessage.template_key == "booking_confirmation"
        )
    )
    await db_session.rollback()
    assert await dispatch(db_session) == 0
    assert delivery == []
    assert (
        await db_session.scalar(
            select(CommunicationMessage.id).where(
                CommunicationMessage.template_key == "booking_confirmation"
            )
        )
        is None
    )


@pytest.mark.asyncio
async def test_accept_validates_resources_and_extended_duration(
    client, db_session, auth_headers, test_clinic
):
    from app.core.auth.service import hash_password
    from app.modules.agenda.models import Cabinet

    professional = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        password_hash=hash_password("Synthetic123!"),
        first_name="Test",
        last_name="Professional",
        is_active=True,
    )
    db_session.add(professional)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=professional.id,
            clinic_id=test_clinic.id,
            role="dentist",
            is_professional=True,
        )
    )
    cabinet = Cabinet(
        id=uuid4(),
        clinic_id=test_clinic.id,
        name="Synthetic room",
        color="#123456",
        display_order=0,
        is_active=True,
    )
    db_session.add(cabinet)
    start = datetime.now(UTC) + timedelta(days=1)
    item = BookingRequest(
        id=uuid4(),
        clinic_id=test_clinic.id,
        professional_id=professional.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="confirmed",
        reason="checkup",
        confirmation_deadline=datetime.now(UTC),
        contact_email="test@example.com",
    )
    db_session.add(item)
    db_session.add(
        Appointment(
            clinic_id=test_clinic.id,
            professional_id=professional.id,
            start_time=start + timedelta(minutes=45),
            end_time=start + timedelta(minutes=75),
            status="scheduled",
        )
    )
    await db_session.commit()
    url = f"/api/v1/online_booking/requests/{item.id}/accept"
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    body = {
        "first_name": "Synthetic",
        "last_name": "",
        "email": None,
        "phone": None,
        "professional_id": str(professional.id),
        "cabinet_id": str(cabinet.id),
        "duration_minutes": 60,
    }
    assert (await client.post(url, headers=headers, json=body)).status_code == 409
    assert (
        await client.post(url, headers=headers, json={**body, "professional_id": str(uuid4())})
    ).status_code == 422
    professional.is_active = False
    await db_session.flush()
    assert (await client.post(url, headers=headers, json=body)).status_code == 422
    professional.is_active = True
    await db_session.flush()
    assert (
        await client.post(url, headers=headers, json={**body, "cabinet_id": str(uuid4())})
    ).status_code == 422
    response = await client.post(url, headers=headers, json={**body, "duration_minutes": 30})
    assert response.status_code == 200, response.text
    appointment = await db_session.get(Appointment, item.appointment_id)
    assert appointment.professional_id == professional.id and appointment.cabinet_id == cabinet.id
    from app.modules.patients.models import Patient

    patient = await db_session.get(Patient, item.patient_id)
    assert patient.email is None and patient.phone is None and patient.last_name == ""
    assert appointment.end_time - appointment.start_time == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_queue_count_and_visit_default(client, db_session, auth_headers, test_clinic):
    now = datetime.now(UTC)
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            slot_minutes=30,
            reasons=[
                {
                    "id": "first_visit",
                    "name_es": "Primera visita",
                    "name_en": "First visit",
                    "duration_minutes": 60,
                    "active": True,
                },
                {
                    "id": "checkup",
                    "name_es": "Revisión",
                    "name_en": "Check-up",
                    "duration_minutes": 45,
                    "active": True,
                },
            ],
        )
    )
    for status, start, reason in (
        ("confirmed", now + timedelta(days=1), "checkup"),
        ("confirmed", now + timedelta(days=2), "first_visit"),
        ("pending_confirmation", now + timedelta(days=3), "checkup"),
        ("confirmed", now - timedelta(minutes=30), "checkup"),
    ):
        db_session.add(
            BookingRequest(
                clinic_id=test_clinic.id,
                professional_id=await clinic_user(db_session, test_clinic.id),
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status=status,
                reason=reason,
                confirmation_deadline=now + timedelta(minutes=10),
            )
        )
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    count = await client.get("/api/v1/online_booking/requests/count", headers=headers)
    assert count.status_code == 200 and count.json()["data"] == 2
    rows = (await client.get("/api/v1/online_booking/requests", headers=headers)).json()["data"]
    assert {row["reason"]: row["default_duration_minutes"] for row in rows} == {
        "checkup": 45,
        "first_visit": 60,
    }


@pytest.mark.asyncio
async def test_patient_suggestions_match_email_or_normalized_phone(
    client, db_session, auth_headers, test_clinic, test_patient
):
    now = datetime.now(UTC)
    test_patient.email = "contact@example.com"
    test_patient.phone = "+34 600-123-456"
    row = BookingRequest(
        clinic_id=test_clinic.id,
        professional_id=await clinic_user(db_session, test_clinic.id),
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, minutes=30),
        status="confirmed",
        reason="checkup",
        confirmation_deadline=now,
        contact_email="CONTACT@example.com",
        contact_phone="34600123456",
    )
    db_session.add(row)
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    url = f"/api/v1/online_booking/requests/{row.id}/patient-suggestions"
    response = await client.get(url, headers=headers)
    assert response.status_code == 200
    assert [p["id"] for p in response.json()["data"]] == [str(test_patient.id)]
    row.contact_email = "different@example.com"
    await db_session.commit()
    response = await client.get(url, headers=headers)
    assert [p["id"] for p in response.json()["data"]] == [str(test_patient.id)]
    assert (
        await client.get(
            f"/api/v1/online_booking/requests/{uuid4()}/patient-suggestions", headers=headers
        )
    ).status_code == 404


@pytest.mark.parametrize(
    "status,blocked",
    [
        ("scheduled", True),
        ("confirmed", True),
        ("checked_in", True),
        ("in_treatment", True),
        ("completed", False),
        ("cancelled", False),
        ("no_show", False),
    ],
)
@pytest.mark.asyncio
async def test_occupied_checks_intervals_and_active_states(
    db_session, test_clinic, status, blocked
):
    from app.modules.online_booking.service import occupied

    professional_id = await db_session.scalar(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
    )
    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(10), UTC)
    appointment = Appointment(
        clinic_id=test_clinic.id,
        professional_id=professional_id,
        cabinet_id=None,
        start_time=start + timedelta(minutes=15),
        end_time=start + timedelta(minutes=45),
        status=status,
    )
    db_session.add(appointment)
    await db_session.flush()
    assert (
        await occupied(
            db_session,
            test_clinic.id,
            start,
            start + timedelta(minutes=30),
            datetime.now(UTC),
            professional_id=professional_id,
        )
        is blocked
    )
    assert not await occupied(
        db_session,
        test_clinic.id,
        start - timedelta(minutes=15),
        start + timedelta(minutes=15),
        datetime.now(UTC),
        professional_id=professional_id,
    )
    assert not await occupied(
        db_session,
        test_clinic.id,
        start + timedelta(minutes=45),
        start + timedelta(minutes=60),
        datetime.now(UTC),
        professional_id=professional_id,
    )


@pytest.mark.parametrize("phase", ["request", "confirm", "accept"])
@pytest.mark.parametrize(
    "resource_case", ["same_professional", "same_cabinet", "different_resources", "null_cabinet"]
)
@pytest.mark.asyncio
async def test_each_booking_phase_checks_only_the_relevant_resources(
    client, db_session, auth_headers, test_clinic, open_hours, phase, resource_case
):
    from app.core.auth.service import hash_password
    from app.modules.agenda.models import Cabinet

    users = [
        User(
            id=uuid4(),
            email=f"{uuid4()}@example.invalid",
            password_hash=hash_password("Synthetic123!"),
            first_name="Test",
            last_name="Dentist",
            is_active=True,
        )
        for _ in range(2)
    ]
    db_session.add_all(users)
    await db_session.flush()
    for user in users:
        db_session.add(
            ClinicMembership(
                id=uuid4(),
                user_id=user.id,
                clinic_id=test_clinic.id,
                role="dentist",
                is_professional=True,
            )
        )
    cabinets = [
        Cabinet(
            id=uuid4(),
            clinic_id=test_clinic.id,
            name=f"Room {n}",
            color="#123456",
            display_order=n,
            is_active=True,
        )
        for n in range(2)
    ]
    db_session.add_all(cabinets)
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=users[0].id,
            public_url="https://example.invalid/booking",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(10), UTC)
    token = "synthetic-token-" + uuid4().hex
    if phase != "request":
        booking = BookingRequest(
            id=uuid4(),
            clinic_id=test_clinic.id,
            professional_id=users[0].id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status="pending_confirmation" if phase == "confirm" else "confirmed",
            reason="checkup",
            token_hash=digest(token) if phase == "confirm" else None,
            confirmation_deadline=datetime.now(UTC) + timedelta(minutes=10),
        )
        db_session.add(booking)
    conflict_professional = users[0].id if resource_case == "same_professional" else users[1].id
    conflict_cabinet = {
        "same_professional": cabinets[1].id,
        "same_cabinet": cabinets[0].id,
        "different_resources": cabinets[1].id,
        "null_cabinet": None,
    }[resource_case]
    appointment = Appointment(
        clinic_id=test_clinic.id,
        professional_id=conflict_professional,
        cabinet_id=conflict_cabinet,
        start_time=start + timedelta(minutes=15),
        end_time=start + timedelta(minutes=45),
        status="scheduled",
    )
    db_session.add(appointment)
    await db_session.commit()
    base = f"/api/v1/online_booking/public/{test_clinic.id}"
    if phase == "request":
        from altcha import Challenge, Payload, solve_challenge

        challenge_response = await client.get(base + "/challenge")
        issued = Challenge.from_dict(challenge_response.json())
        solution = solve_challenge(issued, timeout=20)
        assert solution is not None
        result = await client.post(
            base + "/requests",
            json={
                "altcha": Payload(issued, solution).to_base64(),
                "start_time": start.isoformat(),
                "contact_name": "Synthetic",
                "contact_email": f"{uuid4()}@example.com",
                "contact_phone": "+34600123456",
                "reason": "checkup",
            },
        )
    elif phase == "confirm":
        result = await client.post(base + "/confirm", json={"token": token})
    else:
        result = await client.post(
            f"/api/v1/online_booking/requests/{booking.id}/accept",
            headers={**auth_headers, "X-Clinic-ID": str(test_clinic.id)},
            json={
                "first_name": "Synthetic",
                "last_name": "Patient",
                "professional_id": str(users[0].id),
                "cabinet_id": str(cabinets[0].id),
                "duration_minutes": 30,
            },
        )
    # The configured professional is users[0]. Request and confirmation only
    # see that professional; acceptance also checks the chosen cabinet.
    blocked = resource_case == "same_professional" or (
        phase == "accept" and resource_case == "same_cabinet"
    )
    if blocked:
        assert result.status_code == 409, result.text
    else:
        assert result.status_code in (200, 201), result.text
    if phase == "confirm" and blocked:
        await db_session.refresh(booking)
        assert booking.status == "pending_confirmation" and booking.token_hash == digest(token)
        await db_session.delete(appointment)
        await db_session.flush()
        assert (await client.post(base + "/confirm", json={"token": token})).status_code == 200


@pytest.mark.asyncio
async def test_confirmation_waits_for_concurrent_agenda_write_and_detects_conflict(
    db_session, test_clinic
):
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient

    from app.config import settings
    from app.database import get_db
    from app.main import app
    from app.modules.agenda.service import AppointmentService

    professional_id = await db_session.scalar(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
    )
    start = datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(10), UTC)
    token = "synthetic-token-" + uuid4().hex
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=professional_id,
            public_url="https://example.invalid/booking",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    db_session.add(
        BookingRequest(
            id=uuid4(),
            clinic_id=test_clinic.id,
            professional_id=professional_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status="pending_confirmation",
            reason="checkup",
            token_hash=digest(token),
            confirmation_deadline=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db_session.commit()
    engine = create_async_engine(settings.DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    original = app.dependency_overrides[get_db]

    async def separate_sessions() -> AsyncGenerator:
        async with maker() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = separate_sessions
    try:
        async with maker() as agenda_db:
            await AppointmentService.create_appointment(
                agenda_db,
                test_clinic.id,
                {
                    "professional_id": professional_id,
                    "start_time": start + timedelta(minutes=15),
                    "end_time": start + timedelta(minutes=45),
                    "status": "scheduled",
                },
            )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as parallel:
                task = asyncio.create_task(
                    parallel.post(
                        f"/api/v1/online_booking/public/{test_clinic.id}/confirm",
                        json={"token": token},
                    )
                )
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(task), timeout=0.25)
                await agenda_db.commit()
                response = await asyncio.wait_for(task, timeout=10)
                assert response.status_code == 409, response.text
    finally:
        app.dependency_overrides[get_db] = original
        await engine.dispose()


@pytest.mark.asyncio
async def test_shared_clinic_lock_uses_agenda_namespace():
    from hashlib import blake2b
    from unittest.mock import AsyncMock

    from app.modules.agenda.locks import lock_clinic

    clinic_id = uuid4()
    db = AsyncMock()
    await lock_clinic(db, clinic_id)
    expected = int.from_bytes(
        blake2b(b"agenda:clinic:" + clinic_id.bytes, digest_size=8).digest(),
        byteorder="big",
        signed=True,
    )
    old_key = int.from_bytes(
        blake2b(b"online_booking:clinic:" + clinic_id.bytes, digest_size=8).digest(),
        byteorder="big",
        signed=True,
    )
    assert db.execute.await_args.args[1] == {"lock_key": expected}
    assert expected != old_key


@pytest.mark.asyncio
async def test_altcha_rejects_forgery_expiration_cross_clinic_and_replay(db_session, test_clinic):
    from altcha import Payload, create_challenge, solve_challenge
    from fastapi import HTTPException

    from app.modules.online_booking.captcha import _secret, consume

    async def rejected(proof, clinic_id=test_clinic.id):
        with pytest.raises(HTTPException):
            await consume(db_session, clinic_id, proof)

    await rejected("not-a-payload")
    valid = proof_for(test_clinic.id)
    await rejected(valid, uuid4())
    expired = create_challenge(
        "PBKDF2/SHA-256",
        1000,
        counter=0,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        data={"clinic": str(test_clinic.id)},
        hmac_secret=_secret(test_clinic.id),
    )
    await rejected(Payload(expired, solve_challenge(expired)).to_base64())
    parsed = Payload.from_base64(valid)
    parsed.challenge.parameters.cost = 1
    await rejected(parsed.to_base64())
    await consume(db_session, test_clinic.id, valid)
    with pytest.raises(HTTPException) as replay:
        await consume(db_session, test_clinic.id, valid)
    assert replay.value.status_code == 409


@pytest.mark.asyncio
async def test_altcha_replay_is_atomic_across_transactions(db_session, test_clinic):
    from fastapi import HTTPException

    from app.config import settings
    from app.modules.online_booking.captcha import consume

    encoded = proof_for(test_clinic.id)
    engine = create_async_engine(settings.DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def redeem():
        async with maker() as session:
            try:
                await consume(session, test_clinic.id, encoded)
                await session.commit()
                return 201
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    try:
        assert sorted(await asyncio.gather(redeem(), redeem())) == [201, 409]
    finally:
        await engine.dispose()


def test_contact_phone_and_public_settings_validation():
    from pydantic import ValidationError

    from app.modules.online_booking.schemas import RequestInput, SettingsInput

    body = {
        "start_time": datetime.now(UTC),
        "contact_name": "Synthetic",
        "contact_email": "a@example.com",
        "contact_phone": "600 123 456",
        "reason": "checkup",
        "altcha": "x",
    }
    assert RequestInput(**body).contact_phone == "+34600123456"
    assert (
        RequestInput(**{**body, "contact_phone": "+44 20 7946 0958"}).contact_phone
        == "+442079460958"
    )
    for invalid in ("", "123", "600123456abc"):
        with pytest.raises(ValidationError):
            RequestInput(**{**body, "contact_phone": invalid})
    with pytest.raises(ValidationError):
        RequestInput(**{k: v for k, v in body.items() if k != "contact_phone"})
    assert SettingsInput(accent_color="#123abc", title_es="Citas").title_es == "Citas"
    with pytest.raises(ValidationError):
        SettingsInput(logo_url="https://example.com/logo.png")
    with pytest.raises(ValidationError):
        SettingsInput(accent_color="red")


@pytest.mark.asyncio
async def test_edit_reasons_duration_and_clinic_logo(
    client, db_session, auth_headers, test_clinic, open_hours
):
    import base64

    from app.core.auth.service import hash_password

    professional = User(
        id=uuid4(),
        email=f"{uuid4()}@example.invalid",
        password_hash=hash_password("Synthetic123!"),
        first_name="Test",
        last_name="Dentist",
        is_active=True,
    )
    db_session.add(professional)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=professional.id,
            clinic_id=test_clinic.id,
            role="dentist",
            is_professional=True,
        )
    )
    db_session.add(
        BookingSettings(
            clinic_id=test_clinic.id,
            enabled=True,
            professional_id=professional.id,
            public_url="https://example.invalid/book",
            slot_minutes=30,
            window_days=30,
            min_notice_minutes=0,
        )
    )
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    settings_url = "/api/v1/online_booking/settings"
    data = (await client.get(settings_url, headers=headers)).json()["data"]
    data["reasons"].append(
        {
            "id": "extended",
            "name_es": "Tratamiento largo",
            "name_en": "Long treatment",
            "duration_minutes": 75,
            "active": True,
        }
    )
    assert (await client.put(settings_url, headers=headers, json=data)).status_code == 200
    base = f"/api/v1/online_booking/public/{test_clinic.id}"
    reasons = (await client.get(f"{base}/config")).json()["data"]["reasons"]
    assert reasons[-1]["id"] == "extended" and reasons[-1]["duration_minutes"] == 75
    invalid = {**data, "reasons": data["reasons"] + [data["reasons"][-1]]}
    assert (await client.put(settings_url, headers=headers, json=invalid)).status_code == 422
    removed = {**data, "reasons": data["reasons"][:-1]}
    assert (await client.put(settings_url, headers=headers, json=removed)).status_code == 422
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    start = datetime.combine(tomorrow, time(10), UTC)
    config = await db_session.get(BookingSettings, test_clinic.id)
    await db_session.refresh(config)
    item = BookingRequest(
        id=uuid4(),
        clinic_id=test_clinic.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="pending_confirmation",
        reason="extended",
        confirmation_deadline=datetime.now(UTC) + timedelta(minutes=10),
    )
    await reserve(db_session, test_clinic.id, config, item, datetime.now(UTC))
    assert item.end_time - item.start_time == timedelta(minutes=75)
    import io

    from PIL import Image

    image = Image.new("RGB", (8, 8), "blue")
    exif = Image.Exif()
    exif[270] = "Synthetic secret metadata"
    source = io.BytesIO()
    image.save(source, format="JPEG", exif=exif)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    for filename, raw in (("logo.svg", svg), ("logo.png", svg), ("logo.png", source.getvalue())):
        rejected = await client.put(
            settings_url + "/logo",
            headers=headers,
            json={"filename": filename, "data": base64.b64encode(raw).decode()},
        )
        assert rejected.status_code == 422
    too_large = base64.b64encode(b"x" * (512 * 1024 + 1)).decode()
    assert (
        await client.put(
            settings_url + "/logo",
            headers=headers,
            json={"filename": "logo.png", "data": too_large},
        )
    ).status_code == 422
    response = await client.put(
        settings_url + "/logo",
        headers=headers,
        json={"filename": "logo.jpg", "data": base64.b64encode(source.getvalue()).decode()},
    )
    assert response.status_code == 200
    logo = await client.get(f"{base}/logo")
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert logo.headers["x-content-type-options"] == "nosniff"
    assert logo.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert logo.headers["cache-control"] == "public, max-age=0, must-revalidate"
    assert logo.headers["etag"]
    with Image.open(io.BytesIO(logo.content)) as cleaned:
        assert cleaned.format == "PNG" and not cleaned.getexif()
        assert "exif" not in cleaned.info and "Synthetic secret metadata" not in repr(cleaned.info)
    await db_session.refresh(config)
    config.logo_sanitized = False
    await db_session.flush()
    assert (await client.get(f"{base}/logo")).status_code == 404
    assert (await client.get(f"{base}/config")).json()["data"]["branding"]["logo_url"] is None
    config.logo_sanitized = True
    await db_session.flush()
    cached = await client.get(f"{base}/logo", headers={"If-None-Match": logo.headers["etag"]})
    assert cached.status_code == 304 and cached.content == b""
    assert cached.headers["etag"] == logo.headers["etag"]
    config.enabled = False
    await db_session.flush()
    assert (await client.get(f"{base}/logo")).status_code == 404
    config.enabled = True
    await db_session.flush()
    assert (await client.delete(settings_url + "/logo", headers=headers)).status_code == 200
    assert (await client.get(f"{base}/logo")).status_code == 404


@pytest.mark.asyncio
async def test_availability_respects_existing_clinic_holiday(db_session, test_clinic):
    from app.modules.online_booking.service import slots
    from app.modules.schedules.models import ClinicOverride, ClinicWeeklySchedule, ScheduleShift

    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    db_session.add(weekly)
    await db_session.flush()
    db_session.add(
        ScheduleShift(
            clinic_weekly_id=weekly.id,
            weekday=tomorrow.weekday(),
            start_time=time(9),
            end_time=time(14),
        )
    )
    config = await configure(
        db_session, test_clinic.id, (await professional(db_session, test_clinic.id)).id
    )
    assert await slots(db_session, test_clinic.id, config, tomorrow, datetime.now(UTC))
    db_session.add(
        ClinicOverride(
            clinic_id=test_clinic.id,
            start_date=tomorrow,
            end_date=tomorrow,
            kind="closed",
            reason="Synthetic holiday",
        )
    )
    await db_session.commit()
    assert await slots(db_session, test_clinic.id, config, tomorrow, datetime.now(UTC)) == []
