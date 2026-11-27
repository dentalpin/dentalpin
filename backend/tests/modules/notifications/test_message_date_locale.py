"""Dates in patient messages follow the message's locale (#1211).

Every date in the notification context was ``strftime("%d/%m/%Y")``, so a
Hungarian or German patient read ``14/01/2026`` instead of ``2026. 01. 14.``
or ``14.01.2026``. These run the real context builders (handlers, reminder
sweep, manual send, manual WhatsApp adapter, online booking) with the
patient's preferred locale and read the context the gateway queued. Spanish
keeps ``dd/mm/yyyy``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.agenda.models import Appointment
from app.modules.billing.models import Invoice
from app.modules.budget.models import Budget
from app.modules.notifications import tasks
from app.modules.notifications.channels import Channel, OutboundMessage, SendStatus
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.handlers import NotificationHandlers
from app.modules.notifications.models import CommunicationMessage, NotificationPreference
from app.modules.notifications.service import NotificationService
from app.modules.patients.models import Patient

# 2026-01-15 01:00 UTC is 2026-01-14 19:00 in Mexico City (UTC-6).
START_UTC = datetime(2026, 1, 15, 1, 0, tzinfo=UTC)
ZONE = "America/Mexico_City"

# 2026-01-14 in each locale's own order.
EXPECTED = {
    "es": "14/01/2026",
    "en": "14/01/2026",
    "de": "14.01.2026",
    "hu": "2026. 01. 14.",
}
LOCALES = pytest.mark.parametrize(("locale", "expected"), list(EXPECTED.items()))


async def _prefer(db: AsyncSession, clinic: Clinic, patient: Patient, locale: str) -> None:
    clinic.timezone = ZONE
    db.add(
        NotificationPreference(clinic_id=clinic.id, patient_id=patient.id, preferred_locale=locale)
    )
    await db.flush()


async def _user_id(db: AsyncSession, clinic: Clinic) -> UUID:
    return (
        await db.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic.id)
        )
    ).scalar_one()


async def _appointment(
    db: AsyncSession, clinic: Clinic, patient: Patient, status: str, start: datetime = START_UTC
) -> Appointment:
    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=await _user_id(db, clinic),
        start_time=start,
        end_time=start + timedelta(hours=1),
        status=status,
    )
    db.add(appointment)
    await db.commit()
    return appointment


async def _budget(db: AsyncSession, clinic: Clinic, patient: Patient) -> Budget:
    budget = Budget(
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        status="accepted",
        valid_from=date(2026, 1, 14),
        valid_until=date(2026, 1, 14),
        created_by=await _user_id(db, clinic),
        updated_at=START_UTC,
    )
    db.add(budget)
    await db.commit()
    return budget


async def _context(db: AsyncSession, clinic_id, template_key: str) -> dict:
    row = (
        await db.execute(
            select(CommunicationMessage).where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.template_key == template_key,
            )
        )
    ).scalar_one()
    return row.context_data


@pytest.mark.asyncio
@LOCALES
async def test_appointment_handlers_date_in_patient_locale(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, locale, expected
):
    await _prefer(db_session, test_clinic, test_patient, locale)
    scheduled = await _appointment(db_session, test_clinic, test_patient, "scheduled")
    cancelled = await _appointment(db_session, test_clinic, test_patient, "cancelled")
    clinic_id = str(test_clinic.id)

    await NotificationHandlers.on_appointment_scheduled(
        {"clinic_id": clinic_id, "appointment_id": str(scheduled.id)}, db=db_session
    )
    await NotificationHandlers.on_appointment_cancelled(
        {"clinic_id": clinic_id, "appointment_id": str(cancelled.id)}, db=db_session
    )
    for key in ("appointment_confirmation", "appointment_cancelled"):
        context = await _context(db_session, test_clinic.id, key)
        assert context["locale"] == locale
        assert (context["appointment_date"], context["appointment_time"]) == (expected, "19:00")


@pytest.mark.asyncio
@LOCALES
async def test_reminder_sweep_date_in_patient_locale(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, locale, expected
):
    await _prefer(db_session, test_clinic, test_patient, locale)
    start = (datetime.now(UTC) + timedelta(hours=3)).replace(second=0, microsecond=0)
    await _appointment(db_session, test_clinic, test_patient, "scheduled", start)
    clinic_id = test_clinic.id
    await NotificationService.get_or_create_clinic_settings(db_session, clinic_id)
    await db_session.commit()

    @asynccontextmanager
    async def _session():
        yield db_session

    with patch.object(tasks, "async_session_maker", _session):
        await tasks.process_appointment_reminders()

    local = start.astimezone(ZoneInfo(ZONE)).date()
    context = await _context(db_session, clinic_id, "appointment_reminder")
    assert context["locale"] == locale
    want = {
        "es": local.strftime("%d/%m/%Y"),
        "en": local.strftime("%d/%m/%Y"),
        "de": local.strftime("%d.%m.%Y"),
        "hu": local.strftime("%Y. %m. %d."),
    }[locale]
    assert context["appointment_date"] == want


@pytest.mark.asyncio
@LOCALES
async def test_manual_send_dates_in_patient_locale(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    locale,
    expected,
):
    await _prefer(db_session, test_clinic, test_patient, locale)
    appointment = await _appointment(db_session, test_clinic, test_patient, "scheduled")
    budget = await _budget(db_session, test_clinic, test_patient)
    clinic_id, appointment_id, budget_id = test_clinic.id, appointment.id, budget.id

    response = await client.post(
        "/api/v1/notifications/send",
        # No patient_id: the recipient (and so the locale) comes from the appointment.
        json={"notification_type": "appointment_reminder", "appointment_id": str(appointment_id)},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text
    response = await client.post(
        "/api/v1/notifications/send",
        json={"notification_type": "budget_accepted", "budget_id": str(budget_id)},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text

    reminder = await _context(db_session, clinic_id, "appointment_reminder")
    assert reminder["locale"] == locale
    assert reminder["appointment_date"] == expected
    accepted = await _context(db_session, clinic_id, "budget_accepted")
    assert accepted["locale"] == locale
    assert accepted["budget_date"] == expected
    assert accepted["accepted_date"] == expected


@pytest.mark.asyncio
@LOCALES
async def test_budget_handlers_dates_in_patient_locale(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
    locale,
    expected,
):
    await _prefer(db_session, test_clinic, test_patient, locale)
    budget = await _budget(db_session, test_clinic, test_patient)
    data = {"clinic_id": str(test_clinic.id), "budget_id": str(budget.id)}

    calls: list[dict] = []

    async def _record(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(NotificationGateway, "enqueue", staticmethod(_record))
    await NotificationHandlers.on_budget_sent({**data, "send_method": "email"}, db=db_session)
    await NotificationHandlers.on_budget_accepted(data, db=db_session)
    await NotificationHandlers.on_budget_reminder_sent({**data, "milestone_days": 7}, db=db_session)
    by_type = {c["notification_type"]: c["context"] for c in calls}
    assert by_type["budget_sent"]["budget_date"] == expected
    assert by_type["budget_accepted"]["accepted_date"] == expected
    assert by_type["budget_reminder"]["valid_until"] == expected


@pytest.mark.asyncio
@LOCALES
async def test_invoice_handler_dates_in_patient_locale(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, locale, expected
):
    await _prefer(db_session, test_clinic, test_patient, locale)
    invoice = Invoice(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        invoice_number=f"FAC-{uuid4().hex[:8]}",
        status="issued",
        issue_date=date(2026, 1, 14),
        due_date=date(2026, 1, 14),
        created_by=await _user_id(db_session, test_clinic),
    )
    db_session.add(invoice)
    await db_session.commit()

    await NotificationHandlers.on_invoice_sent(
        {"clinic_id": str(test_clinic.id), "invoice_id": str(invoice.id), "send_method": "email"},
        db=db_session,
    )
    context = await _context(db_session, test_clinic.id, "invoice_sent")
    assert context["locale"] == locale
    assert (context["invoice_date"], context["due_date"]) == (expected, expected)


@pytest.mark.asyncio
@LOCALES
async def test_manual_whatsapp_draft_date_in_message_locale(
    db_session: AsyncSession, test_clinic: Clinic, locale, expected
):
    from app.modules.whatsapp_manual.adapter import ManualWhatsAppAdapter

    test_clinic.timezone = ZONE
    await db_session.flush()
    result = await ManualWhatsAppAdapter().send(
        db_session,
        OutboundMessage(
            Channel.WHATSAPP,
            "+12025550101",
            test_clinic.id,
            "appointment_reminder",
            locale=locale,
            body_text="{{ appointment_date }} {{ appointment_time }}",
            context={"appointment_start_at": START_UTC.isoformat()},
        ),
    )
    assert result.status == SendStatus.DEFERRED
    assert result.body_text == f"{expected} 19:00"


@pytest.mark.asyncio
@LOCALES
async def test_online_booking_email_date_in_requester_locale(
    db_session: AsyncSession, test_clinic: Clinic, locale, expected
):
    from app.modules.online_booking.service import _queue_email

    test_clinic.timezone = ZONE
    await db_session.flush()
    request = SimpleNamespace(
        id=uuid4(),
        contact_name="Alex Example",
        contact_email="alex@example.com",
        start_time=START_UTC,
    )
    await _queue_email(
        db_session, test_clinic.id, request, "appointment_confirmation", locale=locale
    )
    context = await _context(db_session, test_clinic.id, "appointment_confirmation")
    assert context["appointment_date"] == expected
