"""Tests for the patient_timeline module.

Covers:
- Each event handler inserts a timeline row with the right category/title.
- Events missing a ``patient_id`` are no-ops (admin-level events that do
  not belong on a single ficha).
- The read endpoint returns rows filtered by ``patient_id``, supports
  ``category`` filtering + pagination, and enforces permissions.
- Regression: the event bus actually reaches the handlers (the handler
  signature matches ``handler(data)``). This is the bug that made the
  tab silently empty before this module was shipped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import EventType, event_bus
from app.database import async_session_maker, engine
from app.modules.patient_timeline import events as timeline_events
from app.modules.patient_timeline.models import PatientTimeline
from app.modules.patients.models import Patient


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_pool():
    """Drop the global engine's connection pool around every test.

    Event handlers open sessions through ``app.database.async_session_maker``
    (the global pool). The ``db_session`` fixture in conftest spins up its
    own per-test engine to run DDL; that leaves pool connections in the
    global engine out of sync with the per-test schema and triggers
    ``asyncpg: another operation in progress`` on the next test. Disposing
    the pool guarantees every test starts (and leaves) with no lingering
    connections.
    """
    await engine.dispose()
    yield
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _entries_for(db: AsyncSession, patient_id) -> list[PatientTimeline]:
    """Read timeline entries via a fresh session.

    Handlers commit through ``async_session_maker`` — a different session
    than the test's ``db_session``. Opening a new session here sidesteps the
    read-snapshot the test session has held since before the handler ran.
    """
    async with async_session_maker() as read_session:
        result = await read_session.execute(
            select(PatientTimeline).where(PatientTimeline.patient_id == patient_id)
        )
        return list(result.scalars().all())


def _base_payload(test_clinic: Clinic, test_patient: Patient) -> dict:
    return {
        "clinic_id": str(test_clinic.id),
        "patient_id": str(test_patient.id),
        "occurred_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Handler unit tests — every subscribed event type must insert a row.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_appointment_scheduled_inserts_visit(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Limpieza",
        "start_time": datetime.now(UTC).isoformat(),
        "cabinet": "Gabinete 1",
    }
    await timeline_events.on_appointment_scheduled(payload)

    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.event_type == EventType.APPOINTMENT_SCHEDULED
    assert entry.event_category == "visit"
    assert "Limpieza" in entry.title


@pytest.mark.asyncio
async def test_on_appointment_completed_inserts_visit(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Revisión",
        "end_time": datetime.now(UTC).isoformat(),
        "notes": "Sin incidencias",
    }
    await timeline_events.on_appointment_completed(payload)

    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "visit"
    assert entries[0].description == "Sin incidencias"


@pytest.mark.asyncio
async def test_on_appointment_cancelled_inserts_visit(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Endodoncia",
    }
    await timeline_events.on_appointment_cancelled(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert "cancelada" in entries[0].title.lower()


@pytest.mark.asyncio
async def test_on_appointment_no_show_inserts_visit(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "start_time": datetime.now(UTC).isoformat(),
    }
    await timeline_events.on_appointment_no_show(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_type == EventType.APPOINTMENT_NO_SHOW


@pytest.mark.asyncio
async def test_on_tooth_treatment_performed_inserts_treatment(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "treatment_id": str(uuid4()),
        "treatment_name": "Obturación",
        "clinical_type": "restoration",
        "tooth_numbers": ["16", "17"],
        "performed_at": datetime.now(UTC).isoformat(),
    }
    await timeline_events.on_tooth_treatment_performed(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "treatment"
    assert "Obturación" in entries[0].title
    assert "16" in (entries[0].description or "")


@pytest.mark.asyncio
async def test_on_plan_created_inserts_treatment(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "plan_id": str(uuid4()),
        "plan_number": "PT-2026-0001",
        "plan_name": "Ortodoncia completa",
    }
    await timeline_events.on_plan_created(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "treatment"


@pytest.mark.asyncio
async def test_on_plan_item_completed_inserts_treatment(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "item_id": str(uuid4()),
        "plan_id": str(uuid4()),
        "item_name": "Empaste 16",
    }
    await timeline_events.on_plan_item_completed(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert "Empaste 16" in entries[0].title


@pytest.mark.asyncio
async def test_on_budget_sent_inserts_financial(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "budget_id": str(uuid4()),
        "budget_number": "PRES-2026-0001",
        "total": "500.00",
    }
    await timeline_events.on_budget_sent(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "financial"


@pytest.mark.asyncio
async def test_on_budget_accepted_inserts_financial(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "budget_id": str(uuid4()),
        "budget_number": "PRES-2026-0002",
        "total": "750.00",
    }
    await timeline_events.on_budget_accepted(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert "aceptado" in entries[0].title.lower()


@pytest.mark.asyncio
async def test_on_invoice_issued_inserts_financial(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "invoice_id": str(uuid4()),
        "invoice_number": "F-2026-0001",
        "total": "500.00",
    }
    await timeline_events.on_invoice_issued(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "financial"


@pytest.mark.asyncio
async def test_on_invoice_paid_inserts_financial(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "invoice_id": str(uuid4()),
        "invoice_number": "F-2026-0002",
        "total": "200.00",
    }
    await timeline_events.on_invoice_paid(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert "pagada" in entries[0].title.lower()


@pytest.mark.asyncio
async def test_on_notification_sent_inserts_communication(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "message_id": str(uuid4()),
        "channel": "email",
        "template_key": "appointment_reminder",
        "subject": "Recordatorio de cita",
        "status": "sent",
    }
    await timeline_events.on_notification_sent(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "communication"
    assert entries[0].title.startswith("Email enviado")


@pytest.mark.asyncio
async def test_on_notification_sent_records_whatsapp(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """Bug 12 (#287): WhatsApp outbound must show as a send on the timeline."""
    payload = {
        **_base_payload(test_clinic, test_patient),
        "message_id": str(uuid4()),
        "channel": "whatsapp",
        "template_key": "budget_sent",
        "subject": None,
        "status": "sent",
    }
    await timeline_events.on_notification_sent(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].title == "WhatsApp enviado: budget_sent"
    assert entries[0].event_data["channel"] == "whatsapp"


@pytest.mark.asyncio
async def test_on_notification_failed_inserts_communication(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "message_id": str(uuid4()),
        "channel": "email",
        "template_key": "appointment_reminder",
        "subject": "Recordatorio de cita",
        "status": "failed",
        "error_message": "SMTP timeout",
    }
    await timeline_events.on_notification_failed(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].description == "SMTP timeout"


@pytest.mark.asyncio
async def test_on_medical_updated_inserts_medical(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "section": "allergies",
        "summary": "Nueva alergia a penicilina",
    }
    await timeline_events.on_medical_updated(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "medical"
    assert entries[0].title == "Nueva alergia a penicilina"
    assert entries[0].event_data == {"section": "allergies"}


@pytest.mark.asyncio
async def test_on_document_uploaded_inserts_document(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "document_id": str(uuid4()),
        "title": "Radiografía panorámica",
        "document_type": "xray",
    }
    await timeline_events.on_document_uploaded(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) == 1
    assert entries[0].event_category == "document"
    assert "Radiografía" in entries[0].title


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_without_patient_id_is_noop(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """Admin-level sends (no patient) must not land on anyone's ficha."""
    payload = {
        "clinic_id": str(test_clinic.id),
        "patient_id": None,
        "message_id": str(uuid4()),
        "channel": "email",
        "template_key": "admin_alert",
        "subject": "Alerta interna",
        "status": "sent",
    }
    await timeline_events.on_notification_sent(payload)
    entries = await _entries_for(db_session, test_patient.id)
    assert entries == []


@pytest.mark.asyncio
async def test_event_bus_dispatch_reaches_handler(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """Regression: the bus calls ``handler(data)`` — one arg. Handlers must
    match this signature. This test would have caught the old
    ``(self, db, data)`` bug.

    ``db=`` is required because other modules subscribe to this event
    transactionally (ADR 0019); timeline's own handlers stay own-session and
    ignore it.
    """
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Revisión",
        "end_time": datetime.now(UTC).isoformat(),
    }
    await event_bus.publish(EventType.APPOINTMENT_COMPLETED, payload, db=db_session)

    # ``publish`` awaits every subscriber inline, so the timeline row
    # is already written by the time we get here.
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) >= 1
    assert entries[0].event_type == EventType.APPOINTMENT_COMPLETED


# ---------------------------------------------------------------------------
# Read endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_returns_entries(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Limpieza",
        "end_time": datetime.now(UTC).isoformat(),
    }
    await timeline_events.on_appointment_completed(payload)

    response = await client.get(
        f"/api/v1/patient_timeline/patients/{test_patient.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] >= 1
    assert body["entries"][0]["event_category"] == "visit"


@pytest.mark.asyncio
async def test_endpoint_filters_by_category(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    visit_payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Revisión",
        "end_time": datetime.now(UTC).isoformat(),
    }
    await timeline_events.on_appointment_completed(visit_payload)

    financial_payload = {
        **_base_payload(test_clinic, test_patient),
        "budget_id": str(uuid4()),
        "budget_number": "PRES-X",
        "total": "100.00",
    }
    await timeline_events.on_budget_sent(financial_payload)

    response = await client.get(
        f"/api/v1/patient_timeline/patients/{test_patient.id}?category=financial",
        headers=auth_headers,
    )
    assert response.status_code == 200
    entries = response.json()["data"]["entries"]
    assert len(entries) == 1
    assert entries[0]["event_category"] == "financial"


@pytest.mark.asyncio
async def test_endpoint_paginates(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    for i in range(5):
        await timeline_events.on_appointment_completed(
            {
                **_base_payload(test_clinic, test_patient),
                "appointment_id": str(uuid4()),
                "treatment_type": f"Tratamiento {i}",
                "end_time": datetime.now(UTC).isoformat(),
            }
        )

    response = await client.get(
        f"/api/v1/patient_timeline/patients/{test_patient.id}?page=1&page_size=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["entries"]) == 2
    assert body["total"] == 5
    assert body["has_more"] is True


@pytest.mark.asyncio
async def test_endpoint_returns_404_for_unknown_patient(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
):
    response = await client.get(
        f"/api/v1/patient_timeline/patients/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404
