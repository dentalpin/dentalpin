"""Exercise the manual WhatsApp transport and tray with synthetic records."""

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.auth.models import Clinic
from app.core.events import EventType, event_bus
from app.core.plugins.context import ModuleContext
from app.modules.agenda.models import Appointment
from app.modules.notifications.channels import Channel, ChannelAdapter, OutboundMessage, SendStatus
from app.modules.notifications.erasure import NotificationsErasureContributor
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import (
    ClinicChannelSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.patient_timeline.models import PatientTimeline
from app.modules.whatsapp_manual import WhatsappManualModule
from app.modules.whatsapp_manual.adapter import ADAPTER_NAME, ManualWhatsAppAdapter
from app.modules.whatsapp_manual.models import ManualDeliveryDeclaration
from app.modules.whatsapp_manual.service import expire_pending

BASE = "/api/v1/whatsapp_manual"
TEST_MOBILE = "+12025550101"


@pytest.fixture
def now():
    return datetime.now(UTC)


@pytest.fixture
def test_header(auth_headers, test_clinic):
    return {**auth_headers, "X-Clinic-Id": str(test_clinic.id)}


async def _enable(db, clinic_id):
    db.add(
        ClinicChannelSettings(
            clinic_id=clinic_id, channel="whatsapp", adapter_name=ADAPTER_NAME, is_enabled=True
        )
    )
    await db.flush()


async def _consent(db, patient, now):
    db.add(
        NotificationPreference(
            clinic_id=patient.clinic_id, patient_id=patient.id, whatsapp_opt_in_at=now
        )
    )
    await db.flush()


async def _enqueue(db, patient, **kwargs):
    return await NotificationGateway.enqueue(
        db,
        patient.clinic_id,
        "appointment_reminder",
        context={"patient_name": "Alex Example"},
        patient_id=patient.id,
        force_send=True,
        **kwargs,
    )


def _pending(clinic_id, patient_id=None, context=None, **overrides):
    return CommunicationMessage(
        clinic_id=clinic_id,
        patient_id=patient_id,
        context_data=context,
        **{
            "channel": "whatsapp",
            "status": "awaiting_manual",
            "provider": ADAPTER_NAME,
            "to_address": TEST_MOBILE,
            "body_text": "Hola, Alex & equipo.",
            "template_key": "appointment_reminder",
            **overrides,
        },
    )


@pytest.mark.asyncio
async def test_adapter_renders_and_defers(db_session, test_clinic, test_patient, now):
    adapter = ManualWhatsAppAdapter()
    assert isinstance(adapter, ChannelAdapter)
    assert adapter.requires_provider_template is False
    await _enable(db_session, test_patient.clinic_id)
    await _consent(db_session, test_patient, now)
    test_patient.phone = "666 123 456"
    test_clinic.settings = {"country": "ES"}
    db_session.add(
        NotificationTemplate(
            clinic_id=test_patient.clinic_id,
            channel="whatsapp",
            template_key="appointment_reminder",
            locale="es",
            body_text="Hola, {{ patient_name }}.",
        )
    )
    await db_session.flush()

    row = await _enqueue(db_session, test_patient, channels=["whatsapp"])
    assert row.to_address == "+34666123456"
    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert (row.status, row.provider, row.body_text) == (
        "awaiting_manual",
        ADAPTER_NAME,
        "Hola, Alex Example.",
    )
    assert row.sent_at is None
    assert await NotificationGateway.dispatch_outbox(db_session) == 0
    malformed = await adapter.send(
        db_session,
        OutboundMessage(
            Channel.WHATSAPP, TEST_MOBILE, test_patient.clinic_id, "test", body_text="{{ missing }}"
        ),
    )
    assert malformed.status == SendStatus.SKIPPED


@pytest.mark.asyncio
async def test_template_renders_clinic_local_appointment_time(db_session, test_clinic):
    result = await ManualWhatsAppAdapter().send(
        db_session,
        OutboundMessage(
            Channel.WHATSAPP,
            TEST_MOBILE,
            test_clinic.id,
            "appointment_reminder",
            body_text="{{ appointment_date }} {{ appointment_time }}",
            context={"appointment_start_at": "2026-11-17T23:30:00+00:00"},
        ),
    )
    assert result.status == SendStatus.DEFERRED
    assert result.body_text == "18/11/2026 00:30"


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["missing", "opted_out", "do_not_contact"])
async def test_force_send_keeps_contact_blocks(db_session, test_patient, now, condition):
    await _enable(db_session, test_patient.clinic_id)
    if condition == "opted_out":
        db_session.add(
            NotificationPreference(
                clinic_id=test_patient.clinic_id,
                patient_id=test_patient.id,
                whatsapp_enabled=False,
                whatsapp_opt_in_at=now,
            )
        )
    elif condition == "do_not_contact":
        await _consent(db_session, test_patient, now)
        test_patient.do_not_contact = True
    await db_session.flush()

    row = await _enqueue(db_session, test_patient, channels=["whatsapp"])
    assert row.status == "skipped"
    assert await NotificationGateway.dispatch_outbox(db_session) == 0


@pytest.mark.asyncio
async def test_invalid_mobile_falls_back(db_session, test_patient, now):
    await _enable(db_session, test_patient.clinic_id)
    await _consent(db_session, test_patient, now)
    test_patient.phone = "invalid"
    await db_session.flush()

    row = await _enqueue(db_session, test_patient, channels=["whatsapp", "email"])
    assert row.channel == "email"
    assert row.status == "queued"


@pytest.mark.asyncio
async def test_expiry_job_uses_appointment_instant(db_session, test_clinic, now):
    def context(delta):
        return {"appointment_start_at": (now + delta).isoformat()}

    expired = _pending(test_clinic.id, context=context(-timedelta(seconds=1)))
    future = _pending(test_clinic.id, context=context(timedelta(days=1)))
    adhoc = _pending(test_clinic.id)
    malformed = _pending(test_clinic.id, context={"appointment_start_at": "not-a-date"})
    sent = _pending(test_clinic.id, context=context(-timedelta(days=1)), status="sent")
    other_adapter = _pending(test_clinic.id, context=context(-timedelta(days=1)), provider="other")
    rows = [expired, future, adhoc, malformed, sent, other_adapter]
    db_session.add_all(rows)
    await db_session.flush()

    assert await expire_pending(db_session, now) == 1
    assert await expire_pending(db_session, now) == 0
    for row in rows:
        await db_session.refresh(row)
    assert expired.error_message == "appointment_expired"
    assert [row.status for row in rows] == [
        "skipped",
        "awaiting_manual",
        "awaiting_manual",
        "awaiting_manual",
        "sent",
        "awaiting_manual",
    ]


@pytest.mark.asyncio
async def test_tray_open_actions_and_clinic_isolation(
    client, db_session, test_patient, test_header, now
):
    await _enable(db_session, test_patient.clinic_id)
    await _consent(db_session, test_patient, now)
    test_patient.phone = TEST_MOBILE
    foreign = Clinic(name="Other test clinic", tax_id="DEMO-OTHER")
    db_session.add(foreign)
    await db_session.flush()
    first = _pending(test_patient.clinic_id, test_patient.id)
    second = _pending(test_patient.clinic_id, test_patient.id)
    third = _pending(test_patient.clinic_id, test_patient.id)
    outside = _pending(foreign.id)
    db_session.add_all([first, second, third, outside])
    await db_session.commit()

    reply = await client.get(f"{BASE}/tray", headers=test_header)
    assert reply.status_code == 200, reply.text
    assert reply.json()["data"]["total"] == 3
    assert (await client.get(f"{BASE}/count", headers=test_header)).json()["data"] == 3

    reply = await client.post(f"{BASE}/tray/{first.id}/open", headers=test_header)
    assert reply.status_code == 200, reply.text
    url = urlsplit(reply.json()["data"])
    assert (url.scheme, url.netloc, url.path) == ("https", "wa.me", "/12025550101")
    assert parse_qs(url.query)["text"] == [first.body_text]
    assert "%20" in url.query and "+" not in url.query
    assert first.status == "awaiting_manual"
    assert (
        await client.post(f"{BASE}/tray/{outside.id}/open", headers=test_header)
    ).status_code == 404

    async def act(action, *rows):
        return await client.post(
            f"{BASE}/tray/actions",
            headers=test_header,
            json={"action": action, "ids": [str(row.id) for row in rows]},
        )

    assert (await act("mark_sent", first, outside)).status_code == 409
    assert first.status == outside.status == "awaiting_manual"
    sent_events = []

    async def on_sent(payload):
        sent_events.append(payload)

    event_bus.subscribe(EventType.NOTIFICATION_SENT, on_sent)
    try:
        assert (await act("mark_sent", first)).json()["data"] == 1
        declared = await db_session.get(ManualDeliveryDeclaration, first.id)
        assert declared is not None
        first_timestamp = declared.marked_at
        assert (await act("mark_sent", first, second)).json()["data"] == 2
        assert (await act("mark_sent", first)).json()["data"] == 1
    finally:
        event_bus.unsubscribe(EventType.NOTIFICATION_SENT, on_sent)
    assert {event["message_id"] for event in sent_events} == {str(first.id), str(second.id)}
    assert len(sent_events) == 2
    timeline_ids = list(
        await db_session.scalars(
            select(PatientTimeline.source_id).where(
                PatientTimeline.event_type == EventType.NOTIFICATION_SENT,
                PatientTimeline.patient_id == test_patient.id,
            )
        )
    )
    assert len(timeline_ids) == 2
    assert set(timeline_ids) == {first.id, second.id}
    assert (await act("dismiss", third)).json()["data"] == 1
    assert third.status == "skipped"
    assert third.error_message == "dismissed_by_staff"
    assert first.status == second.status == "sent"
    assert first.sent_at
    assert first.delivered_at is None
    assert declared.marked_by_user_id is not None
    assert declared.marked_at == first_timestamp == first.sent_at
    assert not first.context_data
    await NotificationsErasureContributor().erase(
        test_patient.clinic_id, test_patient.id, ["phone"], [], db_session
    )
    await db_session.flush()
    await db_session.refresh(declared)
    assert declared.marked_at == first_timestamp
    assert first.sent_manually is True
    assert first.body_text is None
    assert third.error_message is None
    assert outside.status == "awaiting_manual"


@pytest.mark.asyncio
async def test_staff_queue_uses_current_adapter_and_is_idempotent(
    client, db_session, test_patient, test_header, now
):
    await _enable(db_session, test_patient.clinic_id)
    await _consent(db_session, test_patient, now)
    text = "Literal {{ plain }} & español"
    data = {"patient_id": str(test_patient.id), "request_id": str(uuid4()), "text": text}
    for _ in range(2):
        reply = await client.post(f"{BASE}/drafts", headers=test_header, json=data)
        assert reply.status_code == 202, reply.text
    rows = (await db_session.scalars(select(CommunicationMessage))).all()
    assert len(rows) == 1
    assert rows[0].provider is None
    assert rows[0].triggered_by_user_id

    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert rows[0].body_text == text
    assert rows[0].status == "awaiting_manual"
    assert rows[0].provider == ADAPTER_NAME
    test_patient.do_not_contact = True
    await db_session.flush()
    assert (
        await client.post(f"{BASE}/tray/{rows[0].id}/open", headers=test_header)
    ).status_code == 409

    data["request_id"] = str(uuid4())
    for _ in range(2):
        reply = await client.post(f"{BASE}/drafts", headers=test_header, json=data)
        assert reply.status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(CommunicationMessage)) == 2


@pytest.mark.asyncio
async def test_uninstall_and_reactivate_preserves_communications(db_session, test_clinic):
    await _enable(db_session, test_clinic.id)
    row = _pending(test_clinic.id)
    db_session.add(row)
    await db_session.flush()

    module = WhatsappManualModule()
    ctx = ModuleContext(ADAPTER_NAME, db_session, event_bus, logging.getLogger(__name__))
    try:
        await module.uninstall(ctx)
        assert await db_session.scalar(select(ClinicChannelSettings)) is None
        assert await db_session.get(CommunicationMessage, row.id) is row
        assert not await ManualWhatsAppAdapter().supports(db_session, test_clinic.id)
    finally:
        module.on_activate()
    await _enable(db_session, test_clinic.id)
    assert await ManualWhatsAppAdapter().supports(db_session, test_clinic.id)


@pytest.mark.asyncio
async def test_local_numbers_need_the_clinic_settings_country(db_session, test_clinic):
    adapter = ManualWhatsAppAdapter()
    test_clinic.address = {"country": "ES"}
    test_clinic.timezone = "Europe/Madrid"
    test_clinic.settings = {}
    assert await adapter.normalize_recipient(db_session, test_clinic.id, "666123456") is None
    assert (
        await adapter.normalize_recipient(db_session, test_clinic.id, "+34666123456")
        == "+34666123456"
    )

    test_clinic.settings = {"country": "es"}
    assert (
        await adapter.normalize_recipient(db_session, test_clinic.id, "666123456") == "+34666123456"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["rescheduled", "cancelled", "deleted"])
async def test_appointment_drafts_require_the_original_active_appointment(
    client, db_session, test_patient, test_header, auth_headers, now, change
):
    await _enable(db_session, test_patient.clinic_id)
    await _consent(db_session, test_patient, now)
    test_patient.phone = TEST_MOBILE
    current_user = await client.get("/api/v1/auth/me", headers=auth_headers)
    start = now + timedelta(days=2)
    appointment = Appointment(
        clinic_id=test_patient.clinic_id,
        patient_id=test_patient.id,
        professional_id=current_user.json()["data"]["user"]["id"],
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="scheduled",
    )
    db_session.add(appointment)
    await db_session.flush()
    reply = await client.post(
        f"{BASE}/drafts",
        headers=test_header,
        json={
            "patient_id": str(test_patient.id),
            "appointment_id": str(appointment.id),
            "request_id": str(uuid4()),
            "text": "Texto literal de la cita",
        },
    )
    assert reply.status_code == 202, reply.text
    row = await db_session.scalar(select(CommunicationMessage))
    assert row.template_key == "whatsapp_manual_message"
    assert row.context_data["appointment_id"] == str(appointment.id)
    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    path = f"{BASE}/tray/{row.id}/open"
    assert (await client.post(path, headers=test_header)).status_code == 200

    if change == "rescheduled":
        appointment.start_time += timedelta(hours=1)
        appointment.end_time += timedelta(hours=1)
    elif change == "cancelled":
        appointment.status = "cancelled"
    else:
        await db_session.delete(appointment)
    await db_session.flush()
    reply = await client.post(path, headers=test_header)
    assert reply.status_code == 409, reply.text
    assert reply.json()["message"] == "appointment_changed"
