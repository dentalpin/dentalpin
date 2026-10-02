"""Orthodontics slices a+b: cases, controls, plan link, installments, recalls."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.orthodontics.models import OrthoControl
from app.modules.orthodontics.schemas import (
    OrthoCaseCreate,
    OrthoControlCreate,
    OrthoControlUpdate,
)
from app.modules.orthodontics.service import (
    OrthoCaseService,
    OrthoControlService,
    OrthoSettingsService,
)


async def _professional(db_session, clinic_id, role="dentist"):
    user = User(
        id=uuid4(),
        email=f"ortho-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Orto",
        last_name="Doncista",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role=role))
    await db_session.commit()
    return user


def _case_data(patient_id):
    return OrthoCaseCreate(
        patient_id=patient_id,
        appliance_type="brackets_metal",
        start_date=date(2026, 1, 15),
        estimated_months=18,
    )


@pytest.mark.asyncio
async def test_case_control_lifecycle(db_session: AsyncSession, test_clinic: Clinic, test_patient):
    doc = await _professional(db_session, test_clinic.id)
    case, ann = await OrthoCaseService.create(
        db_session, test_clinic.id, _case_data(test_patient.id)
    )
    await db_session.commit()
    assert case.status == "active"
    assert ann["control_count"] == 0

    control = await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(
            upper_wire="NiTi .014",
            lower_wire="NiTi .012",
            procedures=["power_chain"],
            hygiene="good",
            next_control_weeks=4,
        ),
        performed_by=doc.id,
    )
    await db_session.commit()
    assert control.procedures == ["power_chain"]
    await db_session.refresh(case)
    assert case.current_upper_wire == "NiTi .014"
    assert case.current_lower_wire == "NiTi .012"

    # Null wires leave the in-mouth state untouched.
    await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(procedures=["ligature_change"], next_control_weeks=4),
        performed_by=doc.id,
    )
    await db_session.commit()
    await db_session.refresh(case)
    assert case.current_upper_wire == "NiTi .014"

    found = await OrthoCaseService.get(db_session, test_clinic.id, case.id)
    assert found is not None
    assert found[1]["control_count"] == 2
    assert found[1]["next_due"] is not None

    closed, _ = await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "finished", None
    )
    await db_session.commit()
    assert closed is not None and closed.finished_at is not None

    with pytest.raises(ValueError, match="finished"):
        await OrthoControlService.register(
            db_session,
            test_clinic.id,
            case.id,
            OrthoControlCreate(procedures=[]),
            performed_by=doc.id,
        )


@pytest.mark.asyncio
async def test_non_professional_rejected(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    recep = await _professional(db_session, test_clinic.id, role="receptionist")
    with pytest.raises(ValueError, match="Invalid professional"):
        await OrthoCaseService.create(
            db_session,
            test_clinic.id,
            OrthoCaseCreate(
                patient_id=test_patient.id,
                appliance_type="aligners",
                professional_id=recep.id,
            ),
        )


@pytest.mark.asyncio
async def test_tenancy_isolation(db_session: AsyncSession, test_clinic: Clinic, test_patient):
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    assert await OrthoCaseService.get(db_session, other_clinic.id, case.id) is None
    assert (
        await OrthoCaseService.list_for_patient(db_session, other_clinic.id, test_patient.id) == []
    )


@pytest.mark.asyncio
async def test_settings_seed_idempotent(db_session: AsyncSession, test_clinic: Clinic):
    first = await OrthoSettingsService.get_or_seed(db_session, test_clinic.id)
    await db_session.commit()
    assert len(first.wires) >= 10
    assert "power_chain" in first.procedures
    second = await OrthoSettingsService.get_or_seed(db_session, test_clinic.id)
    await db_session.commit()
    assert first.id == second.id


async def _plan_with_item(db_session, clinic_id, patient_id, professional_id):
    """Build the plan + item through TreatmentPlanService so the item
    carries the real default session (single pending session worth the
    treatment's price snapshot) instead of zero sessions."""
    from app.modules.odontogram.models import Treatment
    from app.modules.treatment_plan.service import TreatmentPlanService

    treatment = Treatment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        clinical_type="orthodontics",
        scope="global_mouth",
        status="planned",
        recorded_at=datetime.now(UTC),
        price_snapshot=Decimal("1200.00"),
    )
    db_session.add(treatment)
    await db_session.flush()
    plan = await TreatmentPlanService.create(
        db_session,
        clinic_id,
        professional_id,
        {"patient_id": patient_id, "title": "Ortho plan"},
    )
    item = await TreatmentPlanService.add_item(
        db_session, clinic_id, plan.id, {"treatment_id": treatment.id}
    )
    await db_session.commit()
    # expire_on_commit=False in this suite: add_item loaded plan.items as
    # empty before the item existed, and the stale collection would shadow
    # the committed row for every later reader in this session. Refresh
    # only that collection (a global expire_all poisons every ORM object
    # the test touches later -> MissingGreenlet on attribute access).
    await db_session.refresh(plan, ["items"])
    return plan, item


async def _recall_count(db_session, clinic_id, patient_id):
    from app.modules.recalls.models import Recall

    result = await db_session.execute(
        select(func.count(Recall.id)).where(
            Recall.clinic_id == clinic_id,
            Recall.patient_id == patient_id,
            Recall.reason == "ortho_review",
        )
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_plan_link_schedule_installments(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()

    plan, item = await _plan_with_item(db_session, test_clinic.id, test_patient.id, doc.id)
    linked, _ = await OrthoCaseService.link_plan(
        db_session, test_clinic.id, case.id, plan.id, item.id
    )
    await db_session.commit()
    assert linked is not None
    assert linked.treatment_plan_id == plan.id
    assert linked.plan_item_id == item.id

    schedule = await OrthoCaseService.generate_schedule(
        db_session, test_clinic.id, case.id, 200.0, 2, 500.0
    )
    await db_session.commit()
    # The item's default session (1200 pending) is REPLACED, not kept
    # alongside the new ones: down 200 + 2 x 500 == 1200 pending.
    assert len(schedule["sessions"]) == 3
    assert schedule["sessions"][0]["label"] == "Down payment"
    assert schedule["sessions"][1]["label"] == "Installment 1"
    assert schedule["pending_count"] == 3
    assert schedule["completed_count"] == 0

    reread = await OrthoCaseService.installments(db_session, test_clinic.id, case.id)
    assert len(reread["sessions"]) == 3


@pytest.mark.asyncio
async def test_generate_schedule_rejects_sum_mismatch(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    plan, item = await _plan_with_item(db_session, test_clinic.id, test_patient.id, doc.id)
    await OrthoCaseService.link_plan(db_session, test_clinic.id, case.id, plan.id, item.id)
    await db_session.commit()
    # 200 + 2 x 100 = 400 against 1200 pending.
    with pytest.raises(ValueError, match="does not match"):
        await OrthoCaseService.generate_schedule(
            db_session, test_clinic.id, case.id, 200.0, 2, 100.0
        )


@pytest.mark.asyncio
async def test_generate_schedule_refuses_completed_sessions(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    from app.modules.treatment_plan.models import PlannedTreatmentItemSession

    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    plan, item = await _plan_with_item(db_session, test_clinic.id, test_patient.id, doc.id)
    await OrthoCaseService.link_plan(db_session, test_clinic.id, case.id, plan.id, item.id)
    await db_session.commit()
    session = (
        (
            await db_session.execute(
                select(PlannedTreatmentItemSession).where(
                    PlannedTreatmentItemSession.plan_item_id == item.id
                )
            )
        )
        .scalars()
        .first()
    )
    session.status = "completed"
    await db_session.commit()
    with pytest.raises(ValueError, match="completed"):
        await OrthoCaseService.generate_schedule(
            db_session, test_clinic.id, case.id, 200.0, 2, 500.0
        )

    unlinked, _ = await OrthoCaseService.unlink_plan(db_session, test_clinic.id, case.id)
    await db_session.commit()
    assert unlinked is not None and unlinked.treatment_plan_id is None

    with pytest.raises(ValueError, match="No treatment plan linked"):
        await OrthoCaseService.installments(db_session, test_clinic.id, case.id)


@pytest.mark.asyncio
async def test_plan_link_second_case_conflicts(
    client, auth_headers, db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    doc = await _professional(db_session, test_clinic.id)
    plan, item = await _plan_with_item(db_session, test_clinic.id, test_patient.id, doc.id)
    first, _ = await OrthoCaseService.create(
        db_session, test_clinic.id, _case_data(test_patient.id)
    )
    second, _ = await OrthoCaseService.create(
        db_session, test_clinic.id, _case_data(test_patient.id)
    )
    await db_session.commit()
    ok = await client.post(
        f"/api/v1/orthodontics/cases/{first.id}/plan-link",
        json={"treatment_plan_id": str(plan.id), "plan_item_id": str(item.id)},
        headers=auth_headers,
    )
    assert ok.status_code == 200, ok.text
    clash = await client.post(
        f"/api/v1/orthodontics/cases/{second.id}/plan-link",
        json={"treatment_plan_id": str(plan.id), "plan_item_id": str(item.id)},
        headers=auth_headers,
    )
    assert clash.status_code == 409


@pytest.mark.asyncio
async def test_plan_link_rejects_foreign_plan(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    with pytest.raises(ValueError, match="Invalid treatment plan"):
        await OrthoCaseService.link_plan(db_session, test_clinic.id, case.id, uuid4(), uuid4())


@pytest.mark.asyncio
async def test_control_creates_recall_unless_paused(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()

    await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(procedures=["power_chain"], next_control_weeks=4),
        performed_by=doc.id,
    )
    await db_session.commit()
    assert await _recall_count(db_session, test_clinic.id, test_patient.id) == 1

    # Duplicate-guard: a second control updates the same pending row.
    await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(procedures=["ipr"], next_control_weeks=6),
        performed_by=doc.id,
    )
    await db_session.commit()
    assert await _recall_count(db_session, test_clinic.id, test_patient.id) == 1

    await OrthoCaseService.change_status(db_session, test_clinic.id, case.id, "paused", None)
    await db_session.commit()
    await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(procedures=["ipr"], next_control_weeks=4),
        performed_by=doc.id,
    )
    await db_session.commit()
    assert await _recall_count(db_session, test_clinic.id, test_patient.id) == 1


@pytest.mark.asyncio
async def test_transferred_out_suggests_plan_close(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    plan, item = await _plan_with_item(db_session, test_clinic.id, test_patient.id, doc.id)
    await OrthoCaseService.link_plan(db_session, test_clinic.id, case.id, plan.id, item.id)
    await db_session.commit()

    moved, annotation = await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "transferred_out", "moved away"
    )
    await db_session.commit()
    assert moved is not None and moved.status == "transferred_out"
    assert annotation["plan_close_suggested"] is True


@pytest.mark.asyncio
async def test_control_appointment_link_validated(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    from app.modules.agenda.models import Appointment

    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    start = datetime.now(UTC) + timedelta(days=1)
    appointment = Appointment(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        professional_id=doc.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="scheduled",
    )
    db_session.add(appointment)
    await db_session.commit()

    control = await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(procedures=[], appointment_id=appointment.id),
        performed_by=doc.id,
    )
    await db_session.commit()
    assert control.appointment_id == appointment.id

    with pytest.raises(ValueError, match="Invalid appointment"):
        await OrthoControlService.register(
            db_session,
            test_clinic.id,
            case.id,
            OrthoControlCreate(procedures=[], appointment_id=uuid4()),
            performed_by=doc.id,
        )


@pytest.mark.asyncio
async def test_list_overdue_and_settings_update(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    doc = await _professional(db_session, test_clinic.id)
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()

    # Control due 6 weeks ago → overdue.
    past = datetime.now(UTC) - timedelta(weeks=10)
    db_session.add(
        OrthoControl(
            clinic_id=test_clinic.id,
            case_id=case.id,
            performed_at=past,
            performed_by=doc.id,
            procedures=[],
            next_control_weeks=4,
        )
    )
    await db_session.commit()

    overdue = await OrthoCaseService.list_overdue(db_session, test_clinic.id)
    assert [c.id for c, _ in overdue] == [case.id]

    # The tool reports the full total even when the limit truncates rows.
    from app.core.agents import AgentContext, AgentMode, tool_registry
    from app.modules.orthodontics.tools import (
        ListOverdueOrthoControlsArgs,
        _list_overdue_ortho_controls,
    )

    case2, _ = await OrthoCaseService.create(
        db_session, test_clinic.id, _case_data(test_patient.id)
    )
    await db_session.commit()
    past2 = datetime.now(UTC) - timedelta(weeks=12)
    db_session.add(
        OrthoControl(
            clinic_id=test_clinic.id,
            case_id=case2.id,
            performed_at=past2,
            performed_by=doc.id,
            procedures=[],
            next_control_weeks=4,
        )
    )
    await db_session.commit()
    ctx = AgentContext(
        agent_id=uuid4(),
        session_id=uuid4(),
        clinic_id=test_clinic.id,
        mode=AgentMode.SUPERVISED,
        permissions=["orthodontics.cases.read"],
        tools=tool_registry,
        db=db_session,
    )
    result = await _list_overdue_ortho_controls(ctx, ListOverdueOrthoControlsArgs(limit=1))
    assert result["total"] == 2
    assert len(result["cases"]) == 1

    settings = await OrthoSettingsService.update(
        db_session, test_clinic.id, ["NiTi .014", "  ", "Steel .016"], ["ipr"]
    )
    await db_session.commit()
    assert settings.wires == ["NiTi .014", "Steel .016"]
    assert settings.procedures == ["ipr"]


@pytest.mark.asyncio
async def test_http_codes(client, auth_headers, test_patient):
    # 201 create, 200 get, 201 control, 422 bogus enum, 404 unknown.
    response = await client.post(
        "/api/v1/orthodontics/cases",
        json={"patient_id": str(test_patient.id), "appliance_type": "aligners"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    case_id = response.json()["data"]["id"]

    response = await client.get(f"/api/v1/orthodontics/cases/{case_id}", headers=auth_headers)
    assert response.status_code == 200
    # The inbox needs to tell cases apart: the patient's name rides along.
    assert response.json()["data"]["patient_name"] == test_patient.full_name

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/controls",
        json={"procedures": ["ipr"], "aligner_number": 3},
        headers=auth_headers,
    )
    assert response.status_code == 201

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/status",
        json={"status": "bogus"},
        headers=auth_headers,
    )
    assert response.status_code == 422

    response = await client.get(f"/api/v1/orthodontics/cases/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404

    # Slice-b: plan link validation + installments without a link.
    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/plan-link",
        json={"treatment_plan_id": str(uuid4()), "plan_item_id": str(uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 400

    response = await client.get(
        f"/api/v1/orthodontics/cases/{case_id}/installments", headers=auth_headers
    )
    assert response.status_code == 400

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/schedule",
        json={"down_payment": 200, "months": 2, "monthly_amount": 100},
        headers=auth_headers,
    )
    assert response.status_code == 400

    # Follow-ups: settings PUT round-trips the chip catalogs.
    response = await client.get("/api/v1/orthodontics/settings", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]["wires"]) >= 10

    response = await client.put(
        "/api/v1/orthodontics/settings",
        json={"wires": ["NiTi .014"], "procedures": ["ipr", "power_chain"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["wires"] == ["NiTi .014"]


async def test_illegal_transition_refused(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "transferred_out", None
    )
    await db_session.commit()
    with pytest.raises(ValueError, match="Cannot move case from 'transferred_out' to 'paused'"):
        await OrthoCaseService.change_status(db_session, test_clinic.id, case.id, "paused", None)


@pytest.mark.asyncio
async def test_reopen_keeps_finished_at(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    await db_session.commit()
    finished, _ = await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "finished", None
    )
    await db_session.commit()
    first_finish = finished.finished_at
    assert first_finish is not None

    reopened, _ = await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "active", "patient returned"
    )
    await db_session.commit()
    assert reopened.status == "active"
    assert reopened.finished_at == first_finish
    assert reopened.reopened_at is not None
    assert reopened.reopened_at >= first_finish

    refinished, _ = await OrthoCaseService.change_status(
        db_session, test_clinic.id, case.id, "finished", None
    )
    await db_session.commit()
    assert refinished.finished_at > first_finish


@pytest.mark.asyncio
async def test_http_illegal_transition_is_400(client, auth_headers, test_patient):
    response = await client.post(
        "/api/v1/orthodontics/cases",
        json={"patient_id": str(test_patient.id), "appliance_type": "aligners"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    case_id = response.json()["data"]["id"]

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/status",
        json={"status": "transferred_out"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    response = await client.post(
        f"/api/v1/orthodontics/cases/{case_id}/status",
        json={"status": "paused"},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_editing_a_control_refreshes_in_mouth_wires(
    db_session: AsyncSession, test_clinic: Clinic, test_patient
):
    case, _ = await OrthoCaseService.create(db_session, test_clinic.id, _case_data(test_patient.id))
    control = await OrthoControlService.register(
        db_session,
        test_clinic.id,
        case.id,
        OrthoControlCreate(upper_wire="NiTi .014", lower_wire="NiTi .014"),
    )
    await OrthoControlService.update(
        db_session, test_clinic.id, control.id, OrthoControlUpdate(upper_wire="NiTi .016")
    )
    await db_session.refresh(case)
    assert case.current_upper_wire == "NiTi .016"
    assert case.current_lower_wire == "NiTi .014"
