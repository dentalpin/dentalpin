"""SMS channel core support tests (roadmap #231 PR1)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    SendStatus,
    channel_registry,
)
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import NotificationPreference
from app.modules.notifications.service import NotificationService


@pytest_asyncio.fixture
async def whatsapp_adapter():
    """A fake WhatsApp adapter that always sends, registered for the test."""

    class FakeWhatsApp:
        channel = Channel.WHATSAPP
        adapter_name = "fake_whatsapp_test"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_whatsapp", provider_message_id="wamid.x"
            )

    adapter = FakeWhatsApp()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("fake_whatsapp_test")


async def _channel_settings(
    db: AsyncSession, clinic_id, preferred: str = "whatsapp", fallback: bool = True
):
    settings = await NotificationService.get_or_create_clinic_settings(db, clinic_id)
    settings.preferred_channel = preferred
    settings.fallback_enabled = fallback
    settings.manual_channels = [preferred]
    await db.commit()
    return settings


@pytest_asyncio.fixture
async def sms_adapter():
    """A fake SMS adapter that always sends, registered for the test."""

    class FakeSms:
        channel = Channel.SMS
        adapter_name = "fake_sms_test"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_sms", provider_message_id="sms.x"
            )

    adapter = FakeSms()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("fake_sms_test")


@pytest.mark.asyncio
async def test_sms_resolves_with_explicit_channel(db_session, test_patient, sms_adapter):
    """SMS rides patients.phone; text-only, no template approval needed."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_phone = test_patient.phone
    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
    )
    assert msg is not None
    assert msg.status == "queued"
    assert msg.channel == "sms"
    assert msg.to_address == patient_phone


@pytest.mark.asyncio
async def test_sms_template_and_session_kinds_resolve(db_session, test_patient, sms_adapter):
    """SMS works as both template and session sends (no Meta-style gate)."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    for kind in ("template", "session"):
        msg = await NotificationGateway.enqueue(
            db_session,
            clinic_id,
            "appointment_confirmation",
            context={},
            patient_id=patient_id,
            channels=["sms"],
            message_kind=kind,
            body_text="hola" if kind == "session" else None,
        )
        assert msg.status == "queued"
        assert msg.channel == "sms"
        assert msg.message_kind == kind


@pytest.mark.asyncio
async def test_explicit_sms_opt_out_blocks_even_force_send(db_session, test_patient, sms_adapter):
    """sms_enabled=False blocks SMS exactly like the whatsapp opt-out."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    db_session.add(
        NotificationPreference(
            clinic_id=clinic_id,
            patient_id=patient_id,
            sms_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
        force_send=True,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "no_viable_channel"


@pytest.mark.asyncio
async def test_sms_opt_out_falls_back_to_email(db_session, test_patient, sms_adapter):
    """Opted-out SMS with fallback enabled lands on email instead."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_email = test_patient.email
    await _channel_settings(db_session, clinic_id, preferred="sms")
    db_session.add(
        NotificationPreference(
            clinic_id=clinic_id,
            patient_id=patient_id,
            sms_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
    )
    assert msg.status == "queued"
    assert msg.channel == "email"
    assert msg.to_address == patient_email


@pytest.mark.asyncio
async def test_do_not_contact_blocks_sms(db_session, test_patient, sms_adapter):
    """do_not_contact is a hard block on SMS like every other channel."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    test_patient.do_not_contact = True
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
        force_send=True,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "do_not_contact"


@pytest.mark.asyncio
async def test_clinic_channels_sms_fallback_order(
    db_session, test_clinic, sms_adapter, whatsapp_adapter
):
    """Preferred SMS + fallback: connected channels follow in enum order."""
    clinic_id = test_clinic.id
    await _channel_settings(db_session, clinic_id, preferred="sms", fallback=True)
    order = await NotificationGateway._clinic_channels(db_session, clinic_id)
    assert order == ["sms", "email", "whatsapp"]


@pytest.mark.asyncio
async def test_sms_rate_limit_skips_when_exhausted(db_session, test_patient, sms_adapter):
    """Second SMS of a 1/day clinic is skipped, not queued."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    settings = await NotificationService.get_or_create_clinic_settings(db_session, clinic_id)
    settings.sms_daily_limit = 1
    await db_session.commit()

    first = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
    )
    assert first.status == "queued"

    second = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_reminder",
        context={},
        patient_id=patient_id,
        channels=["sms"],
    )
    assert second.status == "skipped"
    assert second.error_message == "sms_rate_limited"


@pytest.mark.asyncio
async def test_sms_rate_limit_falls_back_to_next_channel(db_session, test_patient, sms_adapter):
    """An exhausted SMS cap is not a dead end: fallback still reaches email."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_email = test_patient.email
    settings = await _channel_settings(db_session, clinic_id, preferred="sms")
    settings.sms_daily_limit = 0
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
    )
    assert msg.status == "queued"
    assert msg.channel == "email"
    assert msg.to_address == patient_email


@pytest.mark.asyncio
async def test_settings_put_sms_daily_limit_round_trips(client, auth_headers, test_clinic):
    """The persisted cap is echoed back, not the schema default."""
    response = await client.put(
        "/api/v1/notifications/settings",
        json={"sms_daily_limit": 50},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["sms_daily_limit"] == 50

    response = await client.get("/api/v1/notifications/settings", headers=auth_headers)
    assert response.json()["data"]["sms_daily_limit"] == 50


@pytest.mark.asyncio
async def test_manual_send_sms_accepts_phone_only_patient(
    client, auth_headers, test_clinic, db_session, sms_adapter
):
    """POST /notifications/send with channels=["sms"] must not 400 when the
    patient has a phone but no email (issue #392 review)."""
    from uuid import uuid4

    from app.modules.notifications.models import NotificationTemplate
    from app.modules.patients.models import Patient

    patient = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Movil",
        last_name="Solo",
        email=None,
        phone="+34600999888",
    )
    db_session.add(patient)
    db_session.add(
        NotificationTemplate(
            clinic_id=None,
            channel="sms",
            template_key="welcome",
            locale="es",
            body_text="Bienvenido.",
            is_system=True,
        )
    )
    await db_session.commit()
    response = await client.post(
        "/api/v1/notifications/send",
        json={
            "notification_type": "welcome",
            "patient_id": str(patient.id),
            "channels": ["sms"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["success"] is True
