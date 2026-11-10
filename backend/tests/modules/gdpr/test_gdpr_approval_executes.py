"""#686: approving a queued erasure really erases (and only once).

Mirrors the measured run in the issue: a supervised agent asks for a
partial erasure on the documented default guardrails, a supervisor
approves it. Synthetic patient only.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.agents import AgentContext, AgentMode, tool_registry
from app.core.agents.guardrails import reset_counters
from app.core.agents.models import Agent, AgentAuditLog, AgentSession
from app.core.agents.service import ApprovalService
from app.core.auth.models import ClinicMembership
from app.modules.gdpr.schemas import RetentionPolicyCreate
from app.modules.gdpr.service import ErasureService, RetentionService
from app.modules.patients.models import Patient
from tests.modules.gdpr.test_gdpr import erasure_contributors  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_counters():
    reset_counters()
    yield
    reset_counters()


@pytest.mark.asyncio
async def test_approved_erasure_blanks_the_patient_once(
    db_session,
    test_clinic,
    test_patient,
    erasure_contributors,  # noqa: F811
):
    for category in ("email", "phone", "identity"):
        await RetentionService.create(
            db_session,
            test_clinic.id,
            RetentionPolicyCreate(data_category=category, retention_years=0),
        )
    test_patient.national_id = "00000000T"
    await db_session.commit()

    agent = Agent(clinic_id=test_clinic.id, name="a", type="t", mode="supervised", config={})
    db_session.add(agent)
    await db_session.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=test_clinic.id)
    db_session.add(session)
    await db_session.flush()
    ctx = AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=test_clinic.id,
        mode=AgentMode.SUPERVISED,
        permissions=["*"],
        tools=tool_registry,
        db=db_session,
    )

    queued = await tool_registry.call(
        ctx,
        "gdpr.execute_partial_erasure",
        {"patient_id": str(test_patient.id), "categories": ["email", "phone", "identity"]},
    )
    assert queued.error == "pending approval"
    await db_session.refresh(test_patient)
    assert test_patient.email == "patient@test.com"  # not yet

    reviewer_id = (
        (
            await db_session.execute(
                select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .first()
    )
    request_id = queued.data["approval_request_id"]
    from uuid import UUID

    approved = await ApprovalService.approve(
        db_session,
        test_clinic.id,
        UUID(request_id),
        reviewer_id=reviewer_id,
        reviewer_role="admin",
    )

    assert approved.request.status == "executed"
    assert approved.error is None
    await db_session.refresh(test_patient)
    assert test_patient.email is None
    assert test_patient.phone is None
    assert test_patient.national_id is None
    assert (await db_session.get(Patient, test_patient.id)) is not None  # never hard-deleted

    # Second approval: nothing runs, no second erasure-audit row.
    again = await ApprovalService.approve(
        db_session, test_clinic.id, UUID(request_id), reviewer_id=reviewer_id, reviewer_role="admin"
    )
    assert again is None
    logs, _ = await ErasureService.list_audit(db_session, test_clinic.id)
    assert len(logs) == 1
    statuses = (
        (
            await db_session.execute(
                select(AgentAuditLog.status)
                .where(AgentAuditLog.tool_name == "gdpr.execute_partial_erasure")
                .order_by(AgentAuditLog.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert list(statuses) == ["PENDING_APPROVAL", "SUCCESS"]
