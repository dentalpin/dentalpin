"""GDPR erasure contributor: the communication log redacts erased contacts (#546).

The outbox row is also the send audit, so erasure clears the patient's
contact copies (recipient, subject, body) without deleting the row.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.erasure import (
    ERASED_PLACEHOLDER,
    NotificationsErasureContributor,
)
from app.modules.notifications.models import CommunicationMessage
from app.modules.patients.models import Patient


async def _message(
    db: AsyncSession,
    *,
    clinic_id,
    patient_id,
    channel: str,
    to_address: str,
    status: str = "sent",
    **extra,
) -> CommunicationMessage:
    msg = CommunicationMessage(
        clinic_id=clinic_id,
        channel=channel,
        to_address=to_address,
        patient_id=patient_id,
        template_key="appointment_reminder",
        status=status,
        **extra,
    )
    db.add(msg)
    await db.commit()
    return msg


@pytest.mark.asyncio
async def test_email_erasure_redacts_only_email_messages(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    email_msg = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
        subject="Recordatorio de cita",
        body_text="Su cita es el lunes",
    )
    sms_msg = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="sms",
        to_address=test_patient.phone,
        body_text="Recordatorio SMS",
    )

    contributor = NotificationsErasureContributor()
    coverage = await contributor.erase(test_clinic.id, test_patient.id, ["email"], [], db_session)
    await db_session.commit()

    assert coverage.scope == "notifications"
    assert coverage.status == "erased"

    assert email_msg.to_address == ERASED_PLACEHOLDER
    assert email_msg.subject is None
    assert email_msg.body_text is None
    # Phone was not erased: the SMS copy survives untouched.
    assert sms_msg.to_address == test_patient.phone
    assert sms_msg.body_text == "Recordatorio SMS"


@pytest.mark.asyncio
async def test_erasure_cancels_unsent_and_clears_context(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    queued = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
        status="queued",
        context_data={"patient_name": "Ana Test", "locale": "es"},
    )
    failed = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
        status="failed",
        attempts=1,
        error_message="Recipients refused: {'ana@test.com': (550, b'5.1.1 User unknown')}",
    )
    sent = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
        context_data={"patient_name": "Ana Test", "locale": "es"},
    )

    contributor = NotificationsErasureContributor()
    coverage = await contributor.erase(test_clinic.id, test_patient.id, ["email"], [], db_session)
    await db_session.commit()

    assert coverage.scope == "notifications"
    assert coverage.status == "erased"

    # An unsent row is cancelled so the outbox can never dispatch to the
    # placeholder address; a dispatched row stays as the send audit.
    assert queued.status == "skipped"
    assert failed.status == "skipped"
    assert sent.status == "sent"
    # The template context can carry the patient's name; it is cleared too.
    assert queued.context_data is None
    assert sent.context_data is None
    # A failed send persists the refused address in error_message (#546).
    assert failed.error_message is None


@pytest.mark.asyncio
async def test_phone_erasure_redacts_sms_and_whatsapp(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    sms = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="sms",
        to_address=test_patient.phone,
    )
    whatsapp = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="whatsapp",
        to_address=test_patient.phone,
        status="awaiting_manual",
        body_text="Synthetic appointment",
        context_data={"appointment_start_at": "2026-11-20T10:00:00+00:00"},
    )
    email = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
    )

    contributor = NotificationsErasureContributor()
    coverage = await contributor.erase(test_clinic.id, test_patient.id, ["phone"], [], db_session)
    await db_session.commit()

    assert coverage.scope == "notifications"
    assert coverage.status == "erased"

    assert sms.to_address == ERASED_PLACEHOLDER
    assert whatsapp.to_address == ERASED_PLACEHOLDER
    assert whatsapp.status == "skipped"
    assert whatsapp.body_text is None
    assert whatsapp.context_data is None
    # Email was not erased: it survives.
    assert email.to_address == test_patient.email


@pytest.mark.asyncio
async def test_identity_erasure_leaves_contacts_untouched(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    msg = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
    )

    contributor = NotificationsErasureContributor()
    coverage = await contributor.erase(
        test_clinic.id, test_patient.id, ["identity"], [], db_session
    )
    await db_session.commit()

    assert coverage.scope == "notifications"
    assert coverage.status == "not_applicable"

    assert msg.to_address == test_patient.email


@pytest.mark.asyncio
async def test_erasure_does_not_touch_another_patient(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    other = Patient(
        clinic_id=test_clinic.id,
        first_name="Otro",
        last_name="Paciente",
        email="otro@test.com",
    )
    db_session.add(other)
    await db_session.commit()
    other_msg = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=other.id,
        channel="email",
        to_address="otro@test.com",
    )
    mine = await _message(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        channel="email",
        to_address=test_patient.email,
    )

    contributor = NotificationsErasureContributor()
    coverage = await contributor.erase(test_clinic.id, test_patient.id, ["email"], [], db_session)
    await db_session.commit()

    assert coverage.scope == "notifications"
    assert coverage.status == "erased"

    assert other_msg.to_address == "otro@test.com"
    assert mine.to_address == ERASED_PLACEHOLDER
