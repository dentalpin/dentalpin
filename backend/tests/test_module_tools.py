"""Layer B: agent tools for patients + agenda.

Exercises the real tools through the registry chokepoint with a live DB,
covering RBAC parity and multi-tenancy isolation (the two invariants that
make the agent safe).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.context import AgentContext, AgentMode
from app.core.agents.models import Agent, AgentSession
from app.core.agents.tools.registry import tool_registry
from app.modules.patients.service import PatientService


async def _agent_session(db: AsyncSession, clinic_id) -> tuple:
    agent = Agent(clinic_id=clinic_id, name="copilot", type="copilot", mode="autonomous", config={})
    db.add(agent)
    await db.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=clinic_id)
    db.add(session)
    await db.flush()
    return agent, session


async def _ctx(
    db: AsyncSession, clinic_id, permissions: list[str], supervisor_id=None
) -> AgentContext:
    from app.modules.copilot.bridge import COPILOT_GUARDRAILS

    agent, session = await _agent_session(db, clinic_id)
    return AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic_id,
        mode=AgentMode.AUTONOMOUS,
        permissions=permissions,
        tools=tool_registry,
        db=db,
        supervisor_id=supervisor_id,
        # Same policy the copilot bridge runs with: inline confirmation
        # replaces the approval queue (rate limits + denylist stay).
        guardrail_config=COPILOT_GUARDRAILS,
    )


async def _supervisor(db: AsyncSession):
    """A real user row for tools whose audit columns are NOT NULL."""
    from app.core.auth.models import User
    from app.core.auth.service import hash_password

    user = User(
        id=uuid4(),
        email=f"sup-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Super",
        last_name="Visor",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


def test_tools_are_registered() -> None:
    names = tool_registry.list()
    for expected in (
        "patients.search_patients",
        "patients.get_patient",
        "patients.create_patient",
        "agenda.get_day_overview",
        "agenda.book_appointment",
        "agenda.cancel_appointment",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_create_then_search_patient(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["patients.read", "patients.write"])

    created = await tool_registry.call(
        ctx, "patients.create_patient", {"first_name": "María", "last_name": "González"}
    )
    assert created.ok
    assert created.data["full_name"] == "María González"

    found = await tool_registry.call(ctx, "patients.search_patients", {"query": "María"})
    assert found.ok
    assert found.data["total"] >= 1
    assert any(p["full_name"] == "María González" for p in found.data["patients"])


@pytest.mark.asyncio
async def test_create_patient_denied_without_write(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["patients.read"])  # read only
    res = await tool_registry.call(
        ctx, "patients.create_patient", {"first_name": "Ana", "last_name": "Ruiz"}
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


@pytest.mark.asyncio
async def test_search_is_clinic_scoped(db_session, test_clinic) -> None:
    from app.core.auth.models import Clinic

    # Patient belongs to a *different* clinic.
    other = Clinic(id=uuid4(), name="Other Clinic", tax_id="X99999999", settings={})
    db_session.add(other)
    await db_session.flush()
    await PatientService.create_patient(
        db_session, other.id, {"first_name": "Bruno", "last_name": "Otero"}
    )
    await db_session.flush()

    ctx = await _ctx(db_session, test_clinic.id, ["patients.read"])
    res = await tool_registry.call(ctx, "patients.search_patients", {"query": "Bruno"})
    assert res.ok
    assert all(p["full_name"] != "Bruno Otero" for p in res.data["patients"])


@pytest.mark.asyncio
async def test_day_overview_empty(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.read"])
    res = await tool_registry.call(ctx, "agenda.get_day_overview", {"date": "2030-01-01"})
    assert res.ok
    assert res.data["total"] == 0


def test_p0_tools_registered() -> None:
    names = tool_registry.list()
    for expected in (
        "schedules.get_availability",
        "patient_timeline.get_patient_timeline",
        "agenda.get_appointment",
        "agenda.list_cabinets",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_list_cabinets(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.cabinets.read"])
    res = await tool_registry.call(ctx, "agenda.list_cabinets", {})
    assert res.ok
    assert any(c["name"] == "Gabinete 1" for c in res.data["cabinets"])


@pytest.mark.asyncio
async def test_get_availability_runs(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["schedules.availability.read"])
    res = await tool_registry.call(ctx, "schedules.get_availability", {"date": "2030-01-07"})
    assert res.ok
    assert "open_windows" in res.data


@pytest.mark.asyncio
async def test_patient_timeline_empty(db_session, test_clinic) -> None:
    from uuid import uuid4

    ctx = await _ctx(db_session, test_clinic.id, ["patient_timeline.read"])
    res = await tool_registry.call(
        ctx, "patient_timeline.get_patient_timeline", {"patient_id": str(uuid4())}
    )
    assert res.ok
    assert res.data["total"] == 0


def test_financial_tools_registered() -> None:
    names = tool_registry.list()
    for expected in (
        "reports.billing_report",
        "reports.top_clients_by_billing",
        "reports.scheduling_report",
        "payments.payments_summary",
        "payments.collections_by_method",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_billing_report_is_invoice_axis_only(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["reports.billing.read"])
    res = await tool_registry.call(
        ctx, "reports.billing_report", {"date_from": "2025-01-01", "date_to": "2025-12-31"}
    )
    assert res.ok
    assert res.data["total_invoiced"] == 0
    # off-books: never surface the invoiced-vs-paid diff
    assert "total_paid" not in res.data
    assert "total_pending" not in res.data


@pytest.mark.asyncio
async def test_top_clients_empty(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["reports.billing.read"])
    res = await tool_registry.call(ctx, "reports.top_clients_by_billing", {"year": 2025})
    assert res.ok
    assert res.data["clients"] == []


@pytest.mark.asyncio
async def test_payments_summary_is_collection_axis_only(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["payments.reports.read"])
    res = await tool_registry.call(
        ctx, "payments.payments_summary", {"date_from": "2025-01-01", "date_to": "2025-12-31"}
    )
    assert res.ok
    assert res.data["total_collected"] == 0
    # off-books: never surface receivable / what's owed
    assert "clinic_receivable_total" not in res.data
    assert "patient_credit_total" not in res.data


@pytest.mark.asyncio
async def test_financial_denied_without_permission(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["patients.read"])  # no reports perm
    res = await tool_registry.call(
        ctx, "reports.billing_report", {"date_from": "2025-01-01", "date_to": "2025-12-31"}
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


def test_p1_tools_registered() -> None:
    names = tool_registry.list()
    assert "agenda.list_professionals" in names
    assert "schedules.find_free_slots" in names


def test_free_slots_subtract_and_part() -> None:
    from datetime import UTC, datetime

    from app.modules.schedules.tools import _overlaps_part, _subtract

    s = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)
    e = datetime(2030, 1, 1, 13, 0, tzinfo=UTC)
    b0 = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    b1 = datetime(2030, 1, 1, 11, 0, tzinfo=UTC)
    assert _subtract(s, e, [(b0, b1)]) == [(s, b0), (b1, e)]

    morning = (datetime(2030, 1, 1, 9, 0, tzinfo=UTC), datetime(2030, 1, 1, 13, 0, tzinfo=UTC))
    afternoon = (datetime(2030, 1, 1, 16, 0, tzinfo=UTC), datetime(2030, 1, 1, 18, 0, tzinfo=UTC))
    assert _overlaps_part(*morning, "morning") is True
    assert _overlaps_part(*afternoon, "morning") is False
    assert _overlaps_part(*afternoon, "afternoon") is True
    assert _overlaps_part(*morning, "any") is True


@pytest.mark.asyncio
async def test_list_professionals_runs(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.read"])
    res = await tool_registry.call(ctx, "agenda.list_professionals", {})
    assert res.ok
    assert isinstance(res.data["professionals"], list)


@pytest.mark.asyncio
async def test_find_free_slots_runs(db_session, test_clinic) -> None:
    ctx = await _ctx(
        db_session, test_clinic.id, ["schedules.availability.read", "agenda.appointments.read"]
    )
    res = await tool_registry.call(
        ctx, "schedules.find_free_slots", {"professional_id": str(uuid4())}
    )
    assert res.ok
    assert "free_windows" in res.data


@pytest.mark.asyncio
async def test_find_free_slots_needs_agenda_permission(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["schedules.availability.read"])  # missing agenda
    res = await tool_registry.call(
        ctx, "schedules.find_free_slots", {"professional_id": str(uuid4())}
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


async def _appointment_world(db: AsyncSession, clinic_id) -> dict:
    """Dentist + patient + one scheduled appointment with cabinet."""
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import hash_password
    from app.modules.agenda.service import AppointmentService

    dentist = User(
        id=uuid4(),
        email=f"dentist-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Dentist",
        last_name="Tools",
        is_active=True,
    )
    db.add(dentist)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=dentist.id, clinic_id=clinic_id, role="dentist"))
    patient = await PatientService.create_patient(
        db, clinic_id, {"first_name": "Carla", "last_name": "Citas"}
    )
    start = datetime(2031, 3, 3, 10, 0, tzinfo=UTC)
    appt = await AppointmentService.create_appointment(
        db,
        clinic_id,
        {
            "patient_id": patient.id,
            "professional_id": dentist.id,
            "cabinet": "Gabinete 1",
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
    )
    return {"dentist_id": dentist.id, "patient": patient, "appointment": appt, "start": start}


def test_management_tools_registered() -> None:
    names = tool_registry.list()
    for expected in (
        "agenda.reschedule_appointment",
        "agenda.update_appointment_status",
        "patients.update_patient",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_reschedule_appointment(db_session, test_clinic) -> None:
    from datetime import timedelta

    world = await _appointment_world(db_session, test_clinic.id)
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.write"])
    new_start = world["start"] + timedelta(days=1)
    res = await tool_registry.call(
        ctx,
        "agenda.reschedule_appointment",
        {
            "appointment_id": str(world["appointment"].id),
            "start_time": new_start.isoformat(),
            "end_time": (new_start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert res.ok
    assert res.data["start_time"].startswith("2031-03-04T10:00")


@pytest.mark.asyncio
async def test_reschedule_slot_conflict(db_session, test_clinic) -> None:
    from datetime import timedelta

    from app.modules.agenda.service import AppointmentService

    world = await _appointment_world(db_session, test_clinic.id)
    other_start = world["start"] + timedelta(hours=2)
    other = await AppointmentService.create_appointment(
        db_session,
        test_clinic.id,
        {
            "patient_id": world["patient"].id,
            "professional_id": world["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": other_start,
            "end_time": other_start + timedelta(minutes=30),
        },
    )
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.write"])
    # The tool rolls back on conflict; commit first so the rollback can't
    # wipe the fixtures (in production the session/world rows are already
    # committed before a turn runs).
    await db_session.commit()
    res = await tool_registry.call(
        ctx,
        "agenda.reschedule_appointment",
        {
            "appointment_id": str(other.id),
            "start_time": world["start"].isoformat(),
            "end_time": (world["start"] + timedelta(minutes=30)).isoformat(),
        },
    )
    assert res.ok
    assert res.data["error"] == "slot_conflict"


@pytest.mark.asyncio
async def test_update_appointment_status_flow(db_session, test_clinic) -> None:
    world = await _appointment_world(db_session, test_clinic.id)
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.write"])
    appt_id = str(world["appointment"].id)

    res = await tool_registry.call(
        ctx,
        "agenda.update_appointment_status",
        {"appointment_id": appt_id, "to_status": "confirmed"},
    )
    assert res.ok
    assert res.data["status"] == "confirmed"

    # Invalid: confirmed → completed is not allowed; error carries the
    # allowed next states so the model can self-correct.
    res = await tool_registry.call(
        ctx,
        "agenda.update_appointment_status",
        {"appointment_id": appt_id, "to_status": "completed"},
    )
    assert res.ok
    assert res.data["error"] == "invalid_transition"
    assert "checked_in" in res.data["allowed"]

    # Same-state transition.
    res = await tool_registry.call(
        ctx,
        "agenda.update_appointment_status",
        {"appointment_id": appt_id, "to_status": "confirmed"},
    )
    assert res.ok
    assert res.data["error"] == "already_in_state"


@pytest.mark.asyncio
async def test_update_appointment_status_cabinet_required(db_session, test_clinic) -> None:
    from datetime import timedelta

    from app.modules.agenda.service import AppointmentService

    world = await _appointment_world(db_session, test_clinic.id)
    start = world["start"] + timedelta(days=7)
    bare = await AppointmentService.create_appointment(
        db_session,
        test_clinic.id,
        {
            "patient_id": world["patient"].id,
            "professional_id": world["dentist_id"],
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
    )
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.write"])
    res = await tool_registry.call(
        ctx,
        "agenda.update_appointment_status",
        {"appointment_id": str(bare.id), "to_status": "checked_in"},
    )
    assert res.ok and res.data["status"] == "checked_in"
    res = await tool_registry.call(
        ctx,
        "agenda.update_appointment_status",
        {"appointment_id": str(bare.id), "to_status": "in_treatment"},
    )
    assert res.ok
    assert res.data["error"] == "cabinet_required"


@pytest.mark.asyncio
async def test_reschedule_is_clinic_scoped(db_session, test_clinic) -> None:
    from datetime import timedelta

    from app.core.auth.models import Clinic

    world = await _appointment_world(db_session, test_clinic.id)
    other = Clinic(id=uuid4(), name="Other Clinic", tax_id="X88888888", settings={})
    db_session.add(other)
    await db_session.flush()

    ctx = await _ctx(db_session, other.id, ["agenda.appointments.write"])
    new_start = world["start"] + timedelta(days=2)
    res = await tool_registry.call(
        ctx,
        "agenda.reschedule_appointment",
        {
            "appointment_id": str(world["appointment"].id),
            "start_time": new_start.isoformat(),
            "end_time": (new_start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert res.ok
    assert res.data["error"] == "not_found"


@pytest.mark.asyncio
async def test_reschedule_denied_without_write(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.read"])
    res = await tool_registry.call(
        ctx,
        "agenda.reschedule_appointment",
        {
            "appointment_id": str(uuid4()),
            "start_time": "2031-01-01T10:00:00+00:00",
            "end_time": "2031-01-01T10:30:00+00:00",
        },
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


@pytest.mark.asyncio
async def test_update_patient_contact(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["patients.read", "patients.write"])
    created = await tool_registry.call(
        ctx, "patients.create_patient", {"first_name": "Lucía", "last_name": "Vega"}
    )
    assert created.ok
    res = await tool_registry.call(
        ctx,
        "patients.update_patient",
        {"patient_id": created.data["id"], "phone": "+34611222333"},
    )
    assert res.ok
    assert res.data["phone"] == "+34611222333"
    assert res.data["full_name"] == "Lucía Vega"

    res = await tool_registry.call(
        ctx, "patients.update_patient", {"patient_id": created.data["id"]}
    )
    assert res.ok
    assert res.data["error"] == "nothing_to_update"


@pytest.mark.asyncio
async def test_update_patient_denied_without_write(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["patients.read"])
    res = await tool_registry.call(
        ctx, "patients.update_patient", {"patient_id": str(uuid4()), "phone": "+34600000000"}
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


def test_recall_tools_registered() -> None:
    names = tool_registry.list()
    for expected in (
        "recalls.list_due_recalls",
        "recalls.get_recall",
        "recalls.create_recall",
        "recalls.log_contact_attempt",
        "recalls.snooze_recall",
        "recalls.complete_recall",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_recall_create_list_and_duplicate_guard(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["recalls.read", "recalls.write"])
    patient = await PatientService.create_patient(
        db_session, test_clinic.id, {"first_name": "Rita", "last_name": "Recall"}
    )

    created = await tool_registry.call(
        ctx,
        "recalls.create_recall",
        {"patient_id": str(patient.id), "reason": "hygiene", "due_month": "2032-05-15"},
    )
    assert created.ok
    assert created.data["created"] is True
    assert created.data["due_month"] == "2032-05-01"  # normalised to day 1

    # Duplicate guard: same patient+reason while active → updates, created=False.
    dup = await tool_registry.call(
        ctx,
        "recalls.create_recall",
        {"patient_id": str(patient.id), "reason": "hygiene", "due_month": "2032-07-01"},
    )
    assert dup.ok
    assert dup.data["created"] is False
    assert dup.data["id"] == created.data["id"]

    listed = await tool_registry.call(
        ctx, "recalls.list_due_recalls", {"month": "2032-07-20", "limit": 10}
    )
    assert listed.ok
    assert listed.data["total"] == 1
    row = listed.data["recalls"][0]
    assert row["patient_name"] == "Rita Recall"
    assert "reason_note" not in row  # free prose stays out of the list tool


@pytest.mark.asyncio
async def test_recall_list_excludes_do_not_contact(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["recalls.read", "recalls.write"])
    patient = await PatientService.create_patient(
        db_session,
        test_clinic.id,
        {"first_name": "Nuria", "last_name": "NoLlamar", "do_not_contact": True},
    )
    await tool_registry.call(
        ctx,
        "recalls.create_recall",
        {"patient_id": str(patient.id), "reason": "checkup", "due_month": "2032-09-01"},
    )
    listed = await tool_registry.call(ctx, "recalls.list_due_recalls", {"month": "2032-09-01"})
    assert listed.ok
    assert all(r["patient_name"] != "Nuria NoLlamar" for r in listed.data["recalls"])


@pytest.mark.asyncio
async def test_recall_attempt_snooze_complete(db_session, test_clinic) -> None:
    supervisor = await _supervisor(db_session)
    ctx = await _ctx(
        db_session,
        test_clinic.id,
        ["recalls.read", "recalls.write"],
        supervisor_id=supervisor.id,
    )
    patient = await PatientService.create_patient(
        db_session, test_clinic.id, {"first_name": "Aldo", "last_name": "Llamado"}
    )
    created = await tool_registry.call(
        ctx,
        "recalls.create_recall",
        {"patient_id": str(patient.id), "reason": "post_op", "due_month": "2032-03-01"},
    )
    recall_id = created.data["id"]

    res = await tool_registry.call(
        ctx,
        "recalls.log_contact_attempt",
        {"recall_id": recall_id, "channel": "phone", "outcome": "no_answer"},
    )
    assert res.ok
    assert res.data["status"] == "contacted_no_answer"
    assert res.data["contact_attempt_count"] == 1

    res = await tool_registry.call(
        ctx,
        "recalls.log_contact_attempt",
        {"recall_id": recall_id, "channel": "phone", "outcome": "scheduled"},
    )
    assert res.ok
    assert res.data["status"] == "contacted_scheduled"

    res = await tool_registry.call(
        ctx, "recalls.snooze_recall", {"recall_id": recall_id, "months": 2}
    )
    assert res.ok
    assert res.data["due_month"] == "2032-05-01"
    assert res.data["status"] == "pending"

    res = await tool_registry.call(ctx, "recalls.complete_recall", {"recall_id": recall_id})
    assert res.ok
    assert res.data["status"] == "done"

    detail = await tool_registry.call(ctx, "recalls.get_recall", {"recall_id": recall_id})
    assert detail.ok
    assert len(detail.data["attempts"]) == 2


@pytest.mark.asyncio
async def test_recall_write_denied_without_permission(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["recalls.read"])
    res = await tool_registry.call(
        ctx,
        "recalls.create_recall",
        {"patient_id": str(uuid4()), "reason": "hygiene", "due_month": "2032-01-01"},
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


@pytest.mark.asyncio
async def test_recall_tools_clinic_scoped(db_session, test_clinic) -> None:
    from app.core.auth.models import Clinic

    other = Clinic(id=uuid4(), name="Other Clinic", tax_id="X77777777", settings={})
    db_session.add(other)
    await db_session.flush()
    ctx = await _ctx(db_session, test_clinic.id, ["recalls.read", "recalls.write"])
    other_ctx = await _ctx(db_session, other.id, ["recalls.read", "recalls.write"])

    patient = await PatientService.create_patient(
        db_session, test_clinic.id, {"first_name": "Iris", "last_name": "Aislada"}
    )
    created = await tool_registry.call(
        ctx,
        "recalls.create_recall",
        {"patient_id": str(patient.id), "reason": "hygiene", "due_month": "2032-02-01"},
    )
    res = await tool_registry.call(
        other_ctx, "recalls.get_recall", {"recall_id": created.data["id"]}
    )
    assert res.ok
    assert res.data["error"] == "not_found"


def test_money_tools_registered() -> None:
    names = tool_registry.list()
    for expected in (
        "budget.list_budgets",
        "budget.get_budget",
        "budget.send_budget",
        "billing.list_invoices",
        "billing.get_invoice",
        "payments.record_payment",
        "payments.patient_payment_history",
    ):
        assert expected in names


async def _money_world(db: AsyncSession, clinic_id) -> dict:
    """Patient (no email) + user + empty draft budget + draft invoice.

    Also a second budget carrying one real line item: ``get_budget``
    serialises ``budget.items``, so a budget with none never exercises
    that branch — which is how `i.description` survived on a model with
    no such column.
    """
    from datetime import date

    from app.modules.billing.models import Invoice
    from app.modules.budget.models import Budget, BudgetItem
    from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory

    user = await _supervisor(db)
    patient = await PatientService.create_patient(
        db, clinic_id, {"first_name": "Paco", "last_name": "Pagos"}
    )
    budget = Budget(
        clinic_id=clinic_id,
        patient_id=patient.id,
        budget_number="PRES-TEST-0001",
        status="draft",
        valid_from=date(2032, 1, 1),
        created_by=user.id,
    )
    invoice = Invoice(
        clinic_id=clinic_id,
        patient_id=patient.id,
        status="draft",
        created_by=user.id,
    )
    db.add_all([budget, invoice])
    await db.flush()

    category = TreatmentCategory(clinic_id=clinic_id, key="tools-test", names={"es": "Pruebas"})
    db.add(category)
    await db.flush()
    catalog_item = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=category.id,
        internal_code="TOOLS-001",
        names={"es": "Limpieza dental", "en": "Dental cleaning"},
        default_price=50,
    )
    db.add(catalog_item)
    await db.flush()
    lined = Budget(
        clinic_id=clinic_id,
        patient_id=patient.id,
        budget_number="PRES-TEST-0002",
        # Not draft, so the `status: ["draft"]` list assertion above keeps
        # seeing exactly one budget.
        status="rejected",
        valid_from=date(2032, 1, 1),
        created_by=user.id,
    )
    db.add(lined)
    await db.flush()
    db.add(
        BudgetItem(
            clinic_id=clinic_id,
            budget_id=lined.id,
            catalog_item_id=catalog_item.id,
            unit_price=50,
            quantity=2,
            line_subtotal=100,
            line_total=100,
        )
    )
    await db.flush()
    return {
        "user": user,
        "patient": patient,
        "budget": budget,
        "invoice": invoice,
        "lined_budget": lined,
        "catalog_item": catalog_item,
    }


@pytest.mark.asyncio
async def test_budget_tools_and_send_errors(db_session, test_clinic) -> None:
    world = await _money_world(db_session, test_clinic.id)
    ctx = await _ctx(
        db_session,
        test_clinic.id,
        ["budget.read", "budget.write"],
        supervisor_id=world["user"].id,
    )

    listed = await tool_registry.call(ctx, "budget.list_budgets", {"status": ["draft"]})
    assert listed.ok
    assert listed.data["total"] == 1
    assert listed.data["budgets"][0]["patient_name"] == "Paco Pagos"

    detail = await tool_registry.call(
        ctx, "budget.get_budget", {"budget_id": str(world["budget"].id)}
    )
    assert detail.ok
    assert detail.data["items"] == []

    # A budget WITH a line: the branch the empty case cannot reach. It
    # raised AttributeError, because BudgetItem has no `description`
    # column — the line's name lives on its catalog item.
    lined = await tool_registry.call(
        ctx, "budget.get_budget", {"budget_id": str(world["lined_budget"].id)}
    )
    assert lined.ok, lined.error
    assert lined.data["items"] == [
        {"description": "Limpieza dental", "quantity": 2, "total": Decimal("100.00")}
    ]

    # Patient has no email → structured error, no state change.
    res = await tool_registry.call(
        ctx, "budget.send_budget", {"budget_id": str(world["budget"].id), "send_email": True}
    )
    assert res.ok
    assert res.data["error"] == "no_patient_email"

    # Manual delivery of an empty budget → workflow error.
    res = await tool_registry.call(
        ctx, "budget.send_budget", {"budget_id": str(world["budget"].id), "send_email": False}
    )
    assert res.ok
    assert res.data["error"] == "workflow_error"


@pytest.mark.asyncio
async def test_invoice_tools_are_invoice_axis_only(db_session, test_clinic) -> None:
    world = await _money_world(db_session, test_clinic.id)
    ctx = await _ctx(db_session, test_clinic.id, ["billing.read"])

    listed = await tool_registry.call(ctx, "billing.list_invoices", {"status": ["draft"]})
    assert listed.ok
    assert listed.data["total"] == 1
    row = listed.data["invoices"][0]
    # off-books: invoice axis only — no paid/pending amounts, ever.
    for forbidden in ("paid", "total_paid", "pending", "amount_paid"):
        assert forbidden not in row

    detail = await tool_registry.call(
        ctx, "billing.get_invoice", {"invoice_id": str(world["invoice"].id)}
    )
    assert detail.ok
    assert "payments" not in detail.data
    assert "invoice_payments" not in detail.data
    assert detail.data["items"] == []


@pytest.mark.asyncio
async def test_record_payment_and_history(db_session, test_clinic) -> None:
    world = await _money_world(db_session, test_clinic.id)
    ctx = await _ctx(
        db_session,
        test_clinic.id,
        ["payments.record.read", "payments.record.write"],
        supervisor_id=world["user"].id,
    )
    patient_id = str(world["patient"].id)

    # Float JSON amount must coerce to Decimal cleanly.
    res = await tool_registry.call(
        ctx,
        "payments.record_payment",
        {
            "patient_id": patient_id,
            "amount": 50.10,
            "method": "cash",
            "payment_date": "2032-01-10",
            "allocations": [{"target_type": "on_account", "amount": 50.10}],
        },
    )
    assert res.ok
    assert res.data["amount"] == 50.1
    assert res.data["currency"] == "EUR"

    # Allocation sum mismatch → structured workflow error.
    res = await tool_registry.call(
        ctx,
        "payments.record_payment",
        {
            "patient_id": patient_id,
            "amount": 100,
            "method": "card",
            "payment_date": "2032-01-11",
            "allocations": [{"target_type": "on_account", "amount": 60}],
        },
    )
    assert res.ok
    assert res.data["error"] == "workflow_error"

    history = await tool_registry.call(
        ctx, "payments.patient_payment_history", {"patient_id": patient_id}
    )
    assert history.ok
    assert history.data["total_paid"] == 50.1
    assert history.data["on_account_balance"] == 50.1
    assert len(history.data["movements"]) == 1
    # off-books: collection axis only — never the paid-vs-earned diff.
    for forbidden in ("total_earned", "patient_credit", "clinic_receivable"):
        assert forbidden not in history.data


@pytest.mark.asyncio
async def test_record_payment_denied_without_write(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["payments.record.read"])
    res = await tool_registry.call(
        ctx,
        "payments.record_payment",
        {
            "patient_id": str(uuid4()),
            "amount": 10,
            "method": "cash",
            "payment_date": "2032-01-10",
            "allocations": [{"target_type": "on_account", "amount": 10}],
        },
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")


@pytest.mark.asyncio
async def test_budget_tools_clinic_scoped(db_session, test_clinic) -> None:
    from app.core.auth.models import Clinic

    world = await _money_world(db_session, test_clinic.id)
    other = Clinic(id=uuid4(), name="Other Clinic", tax_id="X66666666", settings={})
    db_session.add(other)
    await db_session.flush()
    other_ctx = await _ctx(db_session, other.id, ["budget.read", "billing.read"])

    res = await tool_registry.call(
        other_ctx, "budget.get_budget", {"budget_id": str(world["budget"].id)}
    )
    assert res.ok and res.data["error"] == "not_found"
    res = await tool_registry.call(
        other_ctx, "billing.get_invoice", {"invoice_id": str(world["invoice"].id)}
    )
    assert res.ok and res.data["error"] == "not_found"


def test_free_text_tools_excluded_under_redaction() -> None:
    from app.modules.copilot.bridge import _tool_names_for

    with_free_text = _tool_names_for(["*"], include_free_text=True)
    without = _tool_names_for(["*"], include_free_text=False)
    assert "recalls.get_recall" in with_free_text
    assert "recalls.get_recall" not in without
    assert "recalls.list_due_recalls" in without


@pytest.mark.asyncio
async def test_book_appointment_denied_without_write(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id, ["agenda.appointments.read"])  # no write
    res = await tool_registry.call(
        ctx,
        "agenda.book_appointment",
        {
            "patient_id": str(uuid4()),
            "professional_id": str(uuid4()),
            "start_time": "2030-01-01T10:00:00+00:00",
            "end_time": "2030-01-01T10:30:00+00:00",
        },
    )
    assert res.ok is False
    assert "permission denied" in (res.error or "")
