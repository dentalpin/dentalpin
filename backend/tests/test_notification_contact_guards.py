"""Handler contact guards: email OR phone reaches the gateway (issue #287).

On main every auto-send handler bailed out when the patient had no email,
so phone-only patients silently got nothing — even with WhatsApp installed.
The guard is now "has some contact": the handler always enqueues and the
gateway resolves the concrete channel/address (preferred channel + fallback),
recording an explicit skip when nothing is viable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.notifications.channels import AdapterResult, Channel, SendStatus, channel_registry
from app.modules.notifications.handlers import NotificationHandlers
from app.modules.notifications.models import (
    ClinicNotificationSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.patients.models import Patient


@pytest_asyncio.fixture
async def whatsapp_adapter():
    """A fake WhatsApp adapter that always supports/sends."""

    class FakeWhatsApp:
        channel = Channel.WHATSAPP
        adapter_name = "fake_whatsapp_guards"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_whatsapp", provider_message_id="wamid.g"
            )

    adapter = FakeWhatsApp()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("fake_whatsapp_guards")


async def _make_appointment(db: AsyncSession, clinic_id, patient_id) -> Appointment:
    professional = User(
        email=f"pro-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Pro",
        last_name="Fesional",
    )
    db.add(professional)
    await db.flush()
    appointment = Appointment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        professional_id=professional.id,
        start_time=datetime.now(UTC) + timedelta(days=1),
        end_time=datetime.now(UTC) + timedelta(days=1, hours=1),
        status="scheduled",
    )
    db.add(appointment)
    await db.commit()
    return appointment


async def _rows(db: AsyncSession, clinic_id, template_key: str) -> list[CommunicationMessage]:
    return list(
        (
            await db.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == clinic_id,
                    CommunicationMessage.template_key == template_key,
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_appointment_scheduled_writes_row_for_phone_only_patient(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """Phone-only patient no longer short-circuits the handler: the gateway
    gets to decide, and an outbox row exists (queued or explicit skip)."""
    test_patient.email = None
    await db_session.commit()
    appointment = await _make_appointment(db_session, test_clinic.id, test_patient.id)

    await NotificationHandlers.on_appointment_scheduled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment.id)},
        db=db_session,
    )

    rows = await _rows(db_session, test_clinic.id, "appointment_confirmation")
    assert len(rows) == 1
    assert rows[0].status in ("queued", "skipped")


@pytest.mark.asyncio
async def test_appointment_scheduled_no_row_without_any_contact(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_patient.email = None
    test_patient.phone = None
    await db_session.commit()
    appointment = await _make_appointment(db_session, test_clinic.id, test_patient.id)

    await NotificationHandlers.on_appointment_scheduled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment.id)},
        db=db_session,
    )

    assert await _rows(db_session, test_clinic.id, "appointment_confirmation") == []


@pytest.mark.asyncio
async def test_patient_created_writes_row_for_phone_only_patient(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_patient.email = None
    await db_session.commit()

    await NotificationHandlers.on_patient_created(
        {"clinic_id": str(test_clinic.id), "patient_id": str(test_patient.id)},
        db=db_session,
    )

    rows = await _rows(db_session, test_clinic.id, "welcome")
    assert len(rows) == 1
    assert rows[0].patient_id == test_patient.id


@pytest.mark.asyncio
async def test_phone_only_whatsapp_preferred_queues_whatsapp(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    whatsapp_adapter,
):
    """Full stack: preferred=whatsapp + approved HSM + phone-only patient →
    the confirmation is queued on the whatsapp channel."""
    test_patient.email = None
    await db_session.commit()

    db_session.add(
        ClinicNotificationSettings(
            clinic_id=test_clinic.id,
            preferred_channel="whatsapp",
            fallback_enabled=True,
            manual_channels=["whatsapp", "email"],
        )
    )
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            channel="whatsapp",
            template_key="appointment_confirmation",
            locale="es",
            subject=None,
            body_text="Cita {{appointment_date}}",
            provider_template_name="appointment_confirmation_es",
            provider_template_status="approved",
            is_system=False,
        )
    )
    db_session.add(
        NotificationPreference(
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            whatsapp_enabled=True,
        )
    )
    await db_session.commit()

    appointment = await _make_appointment(db_session, test_clinic.id, test_patient.id)
    await NotificationHandlers.on_appointment_scheduled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment.id)},
        db=db_session,
    )

    rows = await _rows(db_session, test_clinic.id, "appointment_confirmation")
    assert len(rows) == 1
    assert rows[0].status == "queued"
    assert rows[0].channel == "whatsapp"
    assert rows[0].to_address == test_patient.phone


@pytest.mark.asyncio
async def test_budget_accepted_writes_row_for_phone_only_patient(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    from datetime import date
    from decimal import Decimal

    from app.modules.budget.models import Budget

    test_patient.email = None
    await db_session.commit()

    user = User(
        email=f"acc-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="A",
        last_name="B",
    )
    db_session.add(user)
    await db_session.flush()
    budget = Budget(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        budget_number="PRES-ACC-0001",
        status="accepted",
        valid_from=date.today(),
        created_by=user.id,
        total=Decimal("80.00"),
    )
    db_session.add(budget)
    await db_session.commit()

    await NotificationHandlers.on_budget_accepted(
        {"clinic_id": str(test_clinic.id), "budget_id": str(budget.id)},
        db=db_session,
    )

    rows = await _rows(db_session, test_clinic.id, "budget_accepted")
    assert len(rows) == 1
    assert rows[0].patient_id == test_patient.id
