"""#1187: copilot write tools validate like their REST schemas.

Each case goes through ``tool_registry.call`` — the chokepoint the copilot
uses — and pins a gap where the tool accepted what the REST route rejects,
or wrote a different value than the route would.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.context import AgentContext, AgentMode
from app.core.agents.guardrails import reset_counters
from app.core.agents.models import Agent, AgentSession
from app.core.agents.tools.registry import tool_registry
from tests.modules.gdpr.test_gdpr import erasure_contributors  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_counters():
    reset_counters()
    yield
    reset_counters()


async def _ctx(db: AsyncSession, clinic_id, supervisor_id=None) -> AgentContext:
    from app.modules.copilot.bridge import COPILOT_GUARDRAILS

    agent = Agent(clinic_id=clinic_id, name="copilot", type="copilot", mode="autonomous", config={})
    db.add(agent)
    await db.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=clinic_id)
    db.add(session)
    await db.flush()
    return AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic_id,
        mode=AgentMode.AUTONOMOUS,
        permissions=["*"],
        tools=tool_registry,
        db=db,
        supervisor_id=supervisor_id,
        guardrail_config=COPILOT_GUARDRAILS,
    )


async def _user(db: AsyncSession):
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


def _rejected(res, field: str) -> None:
    assert not res.ok, res.data
    assert "validation error" in res.error and field in res.error, res.error


@pytest.mark.asyncio
async def test_index_imaging_study_caps_uid_and_modality(db_session, test_clinic, test_patient):
    ctx = await _ctx(db_session, test_clinic.id)
    base = {"patient_id": str(test_patient.id), "document_id": str(uuid4())}

    res = await tool_registry.call(
        ctx, "imaging_viewer.index_imaging_study", {**base, "modality": "Panoramic radiograph"}
    )
    _rejected(res, "modality")
    res = await tool_registry.call(
        ctx, "imaging_viewer.index_imaging_study", {**base, "study_uid": "1." * 70}
    )
    _rejected(res, "study_uid")


@pytest.mark.asyncio
async def test_patient_tools_require_a_valid_email(db_session, test_clinic, test_patient):
    ctx = await _ctx(db_session, test_clinic.id)

    res = await tool_registry.call(
        ctx,
        "patients.create_patient",
        {"first_name": "Ana", "last_name": "Gil", "email": "not-an-email"},
    )
    _rejected(res, "email")
    res = await tool_registry.call(
        ctx,
        "patients.update_patient",
        {"patient_id": str(test_patient.id), "email": "not-an-email"},
    )
    _rejected(res, "email")


@pytest.mark.asyncio
async def test_lead_tools_reject_blank_names_and_bad_email(db_session, test_clinic):
    from app.modules.leads.service import LeadService

    ctx = await _ctx(db_session, test_clinic.id)
    lead_args = {"full_name": "Marta Ruiz", "phone": "+34 600 999 111", "motive": "Revisión"}

    res = await tool_registry.call(ctx, "leads.create_lead", {**lead_args, "full_name": "   "})
    _rejected(res, "full_name")
    res = await tool_registry.call(ctx, "leads.create_lead", {**lead_args, "email": "nope"})
    _rejected(res, "email")

    lead = await LeadService.create_lead(db_session, test_clinic.id, lead_args)
    res = await tool_registry.call(
        ctx, "leads.update_lead", {"lead_id": str(lead.id), "motive": "  "}
    )
    _rejected(res, "motive")
    res = await tool_registry.call(
        ctx, "leads.update_lead", {"lead_id": str(lead.id), "email": "nope"}
    )
    _rejected(res, "email")
    res = await tool_registry.call(
        ctx,
        "leads.convert_lead_to_patient",
        {"lead_id": str(lead.id), "first_name": " ", "last_name": "Ruiz"},
    )
    _rejected(res, "first_name")
    res = await tool_registry.call(
        ctx,
        "leads.convert_lead_to_patient",
        {"lead_id": str(lead.id), "first_name": "Marta", "last_name": "Ruiz", "email": "x@"},
    )
    _rejected(res, "email")


@pytest.mark.asyncio
async def test_prescription_draft_rejects_blank_medication(db_session, test_clinic, test_patient):
    user = await _user(db_session)
    ctx = await _ctx(db_session, test_clinic.id, supervisor_id=user.id)

    res = await tool_registry.call(
        ctx,
        "prescriptions.create_prescription_draft",
        {"patient_id": str(test_patient.id), "items": [{"medication_name": ""}]},
    )
    _rejected(res, "medication_name")


@pytest.mark.asyncio
async def test_prescription_draft_takes_the_clinic_language(db_session, test_clinic, test_patient):
    from app.modules.prescriptions.models import Prescription

    test_clinic.settings = {**(test_clinic.settings or {}), "communication_language": "en"}
    await db_session.flush()
    user = await _user(db_session)
    ctx = await _ctx(db_session, test_clinic.id, supervisor_id=user.id)

    res = await tool_registry.call(
        ctx,
        "prescriptions.create_prescription_draft",
        {"patient_id": str(test_patient.id), "items": [{"medication_name": "Amoxicilina"}]},
    )
    assert res.ok, res.error
    row = await db_session.get(Prescription, res.data["id"])
    assert row.locale == "en"


async def _erasable(db_session, clinic_id) -> None:
    from app.modules.gdpr.schemas import RetentionPolicyCreate
    from app.modules.gdpr.service import RetentionService

    await RetentionService.create(
        db_session, clinic_id, RetentionPolicyCreate(data_category="email", retention_years=0)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_erasure_audit_names_the_confirming_user(
    db_session,
    test_clinic,
    test_patient,
    erasure_contributors,  # noqa: F811
):
    from app.modules.gdpr.models import ErasureAuditLog

    await _erasable(db_session, test_clinic.id)
    user = await _user(db_session)
    ctx = await _ctx(db_session, test_clinic.id, supervisor_id=user.id)

    res = await tool_registry.call(
        ctx,
        "gdpr.execute_partial_erasure",
        {"patient_id": str(test_patient.id), "categories": ["email"]},
    )
    assert res.ok, res.error
    log = (
        await db_session.execute(
            select(ErasureAuditLog).where(ErasureAuditLog.id == res.data["audit_log_id"])
        )
    ).scalar_one()
    assert log.executed_by == user.id
    assert log.executed_by != ctx.agent_id


@pytest.mark.asyncio
async def test_erasure_without_a_supervisor_is_refused(
    db_session,
    test_clinic,
    test_patient,
    erasure_contributors,  # noqa: F811
):
    from app.modules.gdpr.models import ErasureAuditLog

    await _erasable(db_session, test_clinic.id)
    ctx = await _ctx(db_session, test_clinic.id, supervisor_id=None)

    res = await tool_registry.call(
        ctx,
        "gdpr.execute_partial_erasure",
        {"patient_id": str(test_patient.id), "categories": ["email"]},
    )
    assert "error" in (res.data or {}), res.data
    await db_session.refresh(test_patient)
    assert test_patient.email == "patient@test.com"
    logs = (await db_session.execute(select(ErasureAuditLog))).scalars().all()
    assert logs == []
