"""Booking emails travel through the core notifications gateway (#913)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from booking_helpers import configure, dispatch, professional, proof_for, tomorrow_at
from sqlalchemy import select

from app.modules.notifications.models import ClinicNotificationSettings, CommunicationMessage
from app.modules.online_booking.models import BookingRequest
from app.modules.online_booking.tasks import cleanup


@pytest.mark.asyncio
async def test_confirmation_is_queued_in_the_gateway_and_rendered_from_seeded_templates(
    client, db_session, test_clinic, open_hours, delivery
):
    """Email goes out via the gateway outbox, whatever channel the clinic prefers."""
    configured = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, configured.id)
    db_session.add(
        ClinicNotificationSettings(
            clinic_id=test_clinic.id, preferred_channel="whatsapp", fallback_enabled=False
        )
    )
    await db_session.commit()
    response = await client.post(
        f"/api/v1/online_booking/public/{test_clinic.id}/requests",
        json={
            "start_time": tomorrow_at(16).isoformat(),
            "contact_name": "Synthetic <b>",
            "contact_email": "locale@example.com",
            "contact_phone": "+34600123456",
            "reason": "checkup",
            "altcha": proof_for(test_clinic.id),
        },
    )
    assert response.status_code == 201, response.text
    queued = await db_session.scalar(select(CommunicationMessage))
    assert queued.status == "queued" and queued.channel == "email"
    assert queued.template_key == "booking_confirmation"
    assert await dispatch(db_session) == 1
    sent = delivery[0]
    assert sent.to_email == "locale@example.com"
    assert "&lt;b&gt;" in sent.body_html and "<b>" not in sent.body_html.split("<h2>")[1]
    assert "#token=" in sent.body_text and "&amp;" not in sent.body_text
    # The template does not repeat the other locale's footer wording.
    assert "Este email fue enviado por" in sent.body_html


@pytest.mark.asyncio
async def test_english_clinics_get_english_copy(
    client, db_session, test_clinic, open_hours, delivery
):
    from app.core.auth.models import Clinic

    clinic = await db_session.get(Clinic, test_clinic.id)
    clinic.settings = {**(clinic.settings or {}), "communication_language": "en"}
    configured = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, configured.id)
    response = await client.post(
        f"/api/v1/online_booking/public/{test_clinic.id}/requests",
        json={
            "start_time": tomorrow_at(16).isoformat(),
            "contact_name": "Synthetic",
            "contact_email": "english@example.com",
            "language": "en",
            "contact_phone": "+34600123456",
            "reason": "checkup",
            "altcha": proof_for(test_clinic.id),
        },
    )
    assert response.status_code == 201, response.text
    assert await dispatch(db_session) == 1
    assert delivery[0].subject.startswith("Confirm your appointment request at ")
    assert "This email was sent by" in delivery[0].body_html


@pytest.mark.asyncio
async def test_cleanup_cancels_a_queued_confirmation_for_a_closed_request(
    client, db_session, test_clinic, open_hours, delivery
):
    configured = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, configured.id)
    response = await client.post(
        f"/api/v1/online_booking/public/{test_clinic.id}/requests",
        json={
            "start_time": tomorrow_at(17).isoformat(),
            "contact_name": "Synthetic",
            "contact_email": "closed@example.com",
            "contact_phone": "+34600123456",
            "reason": "checkup",
            "altcha": proof_for(test_clinic.id),
        },
    )
    assert response.status_code == 201, response.text
    row = await db_session.scalar(select(BookingRequest))
    row.confirmation_deadline = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    await cleanup()
    assert await dispatch(db_session) == 0
    assert delivery == []
    db_session.expire_all()
    message = await db_session.scalar(select(CommunicationMessage))
    assert message.status == "skipped" and message.context_data == {}


@pytest.mark.asyncio
async def test_rolled_back_request_queues_no_email(db_session, test_clinic, open_hours, delivery):
    """The gateway enqueues inside the caller's transaction: no commit, no mail."""
    from app.modules.online_booking.schemas import RequestInput
    from app.modules.online_booking.service import BookingService

    configured = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, configured.id)
    await BookingService.create_request(
        db_session,
        test_clinic.id,
        RequestInput(
            start_time=tomorrow_at(10),
            contact_name="Synthetic",
            contact_email="rollback@example.com",
            contact_phone="+34600123456",
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
    assert await db_session.scalar(select(CommunicationMessage.id)) is None
