"""A booking-created patient does not receive the generic welcome message."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.notifications.handlers import NotificationHandlers
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService


@pytest.mark.asyncio
async def test_welcome_flag_only_suppresses_welcome(db_session, test_clinic):
    patient = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Synthetic",
        last_name="Patient",
        email="synthetic@example.invalid",
    )
    db_session.add(patient)
    await db_session.flush()
    payload = {"patient_id": str(patient.id), "clinic_id": str(test_clinic.id)}
    with patch(
        "app.modules.notifications.gateway.NotificationGateway.enqueue", new_callable=AsyncMock
    ) as enqueue:
        await NotificationHandlers.on_patient_created(
            {**payload, "send_welcome": False}, db=db_session
        )
        enqueue.assert_not_awaited()
        await NotificationHandlers.on_patient_created(payload, db=db_session)
        assert enqueue.await_count == 1
        assert enqueue.await_args.kwargs["notification_type"] == "welcome"


@pytest.mark.asyncio
async def test_patient_creation_publishes_welcome_choice_without_changing_other_fields(
    db_session, test_clinic
):
    with patch("app.modules.patients.service.event_bus.publish", new_callable=AsyncMock) as publish:
        patient = await PatientService.create_patient(
            db_session,
            test_clinic.id,
            {"first_name": "Synthetic", "last_name": "Patient"},
            send_welcome=False,
        )
        payload = publish.await_args.args[1]
        assert payload["patient_id"] == str(patient.id)
        assert payload["clinic_id"] == str(test_clinic.id)
        assert payload["send_welcome"] is False


@pytest.mark.asyncio
async def test_default_patient_creation_keeps_existing_event_payload(db_session, test_clinic):
    with patch("app.modules.patients.service.event_bus.publish", new_callable=AsyncMock) as publish:
        patient = await PatientService.create_patient(
            db_session, test_clinic.id, {"first_name": "Synthetic", "last_name": "Patient"}
        )
        assert publish.await_args.args[1] == {
            "patient_id": str(patient.id),
            "clinic_id": str(test_clinic.id),
        }
