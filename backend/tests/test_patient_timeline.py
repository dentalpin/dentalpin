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
    await timeline_events.on_appointment_scheduled(payload, db=db_session)
    await db_session.commit()

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
    await timeline_events.on_appointment_completed(payload, db=db_session)
    await db_session.commit()

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
    await timeline_events.on_appointment_cancelled(payload, db=db_session)
    await db_session.commit()
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
    await timeline_events.on_appointment_no_show(payload, db=db_session)
    await db_session.commit()
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
    transactionally (ADR 0019); the appointment lifecycle handlers take the
    publisher's session rather than opening their own.
    """
    payload = {
        **_base_payload(test_clinic, test_patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Revisión",
        "end_time": datetime.now(UTC).isoformat(),
    }
    await event_bus.publish(EventType.APPOINTMENT_COMPLETED, payload, db=db_session)
    # The handler writes in this transaction, so the row becomes visible to
    # another session only after we commit — that is the contract now.
    await db_session.commit()

    # ``publish`` awaits every subscriber inline, so the timeline row
    # is already written by the time we get here.
    entries = await _entries_for(db_session, test_patient.id)
    assert len(entries) >= 1
    assert entries[0].event_type == EventType.APPOINTMENT_COMPLETED


@pytest.mark.asyncio
async def test_confirmed_lands_when_the_patient_is_not_committed_yet(
    db_session: AsyncSession, test_clinic: Clinic
):
    """A booking can create the patient and confirm the appointment in one
    transaction, so the entry must be written inside that transaction.

    A handler that opens its own session cannot see the uncommitted patient:
    the FK on ``patient_timeline.patient_id`` fails, the insert rolls back and
    the visit disappears from the ficha without a trace. This test creates the
    patient without committing, publishes, then commits — before the handler
    was made transactional it left zero entries behind.
    """
    patient = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Uncommitted",
        last_name="Patient",
        email="uncommitted@test.com",
        phone="+34600000001",
    )
    db_session.add(patient)
    await db_session.flush()  # the row exists, but only inside this transaction

    payload = {
        **_base_payload(test_clinic, patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Revisión",
        "changed_at": datetime.now(UTC).isoformat(),
    }
    await event_bus.publish(EventType.APPOINTMENT_CONFIRMED, payload, db=db_session)
    await db_session.commit()

    entries = await _entries_for(db_session, patient.id)
    assert [e.event_type for e in entries] == [EventType.APPOINTMENT_CONFIRMED]


@pytest.mark.asyncio
async def test_scheduled_lands_when_the_patient_is_not_committed_yet(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The booking path: create_appointment publishes APPOINTMENT_SCHEDULED
    with ``db=db`` while the patient it just created is still uncommitted.

    The timeline entry must share that transaction. A handler on its own
    session cannot see the uncommitted patient, the FK on
    ``patient_timeline.patient_id`` fails, and the visit never reaches the
    ficha. Before the handler was made transactional this left zero entries.
    """
    patient = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Uncommitted",
        last_name="Booking",
        email="uncommitted-booking@test.com",
        phone="+346****0002",
    )
    db_session.add(patient)
    await db_session.flush()  # exists only inside this transaction

    payload = {
        **_base_payload(test_clinic, patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Limpieza",
        "start_time": datetime.now(UTC).isoformat(),
    }
    await event_bus.publish(EventType.APPOINTMENT_SCHEDULED, payload, db=db_session)
    await db_session.commit()

    entries = await _entries_for(db_session, patient.id)
    assert [e.event_type for e in entries] == [EventType.APPOINTMENT_SCHEDULED]


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
    await timeline_events.on_appointment_completed(payload, db=db_session)
    await db_session.commit()

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
    await timeline_events.on_appointment_completed(visit_payload, db=db_session)
    await db_session.commit()

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
            },
            db=db_session,
        )
    await db_session.commit()

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


@pytest.mark.asyncio
async def test_a_timeline_failure_does_not_abort_the_publisher(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch
):
    """The savepoint keeps issue #183 intact: the log cannot kill what it logs.

    Transactional handlers write inside the publisher's transaction, which is
    what makes an uncommitted patient visible to the insert. Wrapping the
    insert in a savepoint means a failed timeline write rolls back only the
    savepoint, so the appointment still commits — same-transaction visibility
    without the payload-only guarantee being lost.
    """
    patient = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Savepoint",
        last_name="Survivor",
        email="savepoint-survivor@test.com",
        phone="+34600111223",
    )
    db_session.add(patient)
    await db_session.flush()  # exists only inside this transaction

    async def _boom(*args, **kwargs):
        raise RuntimeError("timeline is down")

    monkeypatch.setattr(timeline_events.TimelineService, "add_entry", _boom)

    payload = {
        **_base_payload(test_clinic, patient),
        "appointment_id": str(uuid4()),
        "treatment_type": "Limpieza",
        "start_time": datetime.now(UTC).isoformat(),
    }
    await event_bus.publish(EventType.APPOINTMENT_SCHEDULED, payload, db=db_session)
    await db_session.commit()  # must not raise: the booking outlives the log

    assert await _entries_for(db_session, patient.id) == []
    assert await db_session.get(Patient, patient.id) is not None


# ---------------------------------------------------------------------------
# Clinical notes (#1155) — every note event clinical_notes publishes reaches
# the timeline, and the stored event_type is the real event name.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("note_type", "event_name"),
    [
        ("administrative", EventType.CLINICAL_NOTE_ADMINISTRATIVE_CREATED),
        ("diagnosis", EventType.CLINICAL_NOTE_DIAGNOSIS_CREATED),
        ("treatment", EventType.CLINICAL_NOTE_TREATMENT_CREATED),
        ("treatment_plan", EventType.CLINICAL_NOTE_PLAN_CREATED),
        ("appointment_clinical", EventType.CLINICAL_NOTE_APPOINTMENT_CLINICAL_CREATED),
        (
            "appointment_administrative",
            EventType.CLINICAL_NOTE_APPOINTMENT_ADMINISTRATIVE_CREATED,
        ),
    ],
)
async def test_every_clinical_note_event_lands_with_its_own_event_type(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    note_type: str,
    event_name: str,
):
    payload = {
        **_base_payload(test_clinic, test_patient),
        "note_id": str(uuid4()),
        "note_type": note_type,
        "owner_type": "patient",
        "owner_id": str(test_patient.id),
        "body_excerpt": "nota",
    }
    await event_bus.publish(event_name, payload)

    entries = await _entries_for(db_session, test_patient.id)
    assert [(e.event_type, e.event_category) for e in entries] == [(str(event_name), "note")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("note_type", "title"),
    [
        ("appointment_clinical", "Nota clínica de cita"),
        ("appointment_administrative", "Nota administrativa de cita"),
    ],
)
async def test_note_written_on_an_appointment_reaches_the_timeline(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    note_type: str,
    title: str,
):
    """Through the real route: the note's owner is the appointment, the
    timeline row lands on the appointment's patient."""
    from app.modules.agenda.service import AppointmentService

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    start = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    apt = await AppointmentService.create_appointment(
        db_session,
        test_clinic.id,
        {
            "patient_id": test_patient.id,
            "professional_id": user_id,
            "start_time": start,
            "end_time": start.replace(minute=30),
        },
        created_by=user_id,
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/clinical_notes/notes",
        headers=auth_headers,
        json={
            "note_type": note_type,
            "owner_type": "appointment",
            "owner_id": str(apt.id),
            "body": "<p>Dolor en el 46</p>",
        },
    )
    assert resp.status_code == 201, resp.text
    note_id = resp.json()["data"]["id"]
    await db_session.commit()

    entries = await _entries_for(db_session, test_patient.id)
    notes = [e for e in entries if e.source_table == "clinical_notes"]
    assert len(notes) == 1, [e.event_type for e in entries]
    assert str(notes[0].source_id) == note_id
    assert notes[0].event_type == f"clinical_notes.{note_type}_created"
    assert notes[0].title == title
    assert notes[0].description == "Dolor en el 46"
