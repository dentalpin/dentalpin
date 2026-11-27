"""The copilot's ``generate_document`` tool validates like ``POST /documents`` (#1182)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.context import AgentContext, AgentMode
from app.core.agents.models import Agent, AgentSession
from app.core.agents.tools.registry import tool_registry
from app.modules.documents.models import GeneratedDocument

TOOL = "documents.generate_document"


async def _ctx(db: AsyncSession, clinic_id) -> AgentContext:
    from app.core.auth.models import User
    from app.core.auth.service import hash_password
    from app.modules.copilot.bridge import COPILOT_GUARDRAILS

    user = User(
        id=uuid4(),
        email=f"sup-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Super",
        last_name="Visor",
        is_active=True,
    )
    db.add(user)

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
        permissions=["documents.write"],
        tools=tool_registry,
        db=db,
        supervisor_id=user.id,
        guardrail_config=COPILOT_GUARDRAILS,
    )


async def _doc_count(db: AsyncSession, clinic_id) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(GeneratedDocument)
        .where(GeneratedDocument.clinic_id == clinic_id)
    )


@pytest.mark.asyncio
async def test_prescription_with_string_medications_is_refused(
    db_session, test_clinic, test_patient
) -> None:
    ctx = await _ctx(db_session, test_clinic.id)

    res = await tool_registry.call(
        ctx,
        TOOL,
        {
            "patient_id": str(test_patient.id),
            "document_type": "prescription",
            "title": "Amoxicilina",
            "content": {"medications": ["Amoxicilina 500 mg cada 8 h, 7 dias"]},
        },
    )

    assert res.ok
    assert res.data["error"] == "invalid"
    assert "medications" in res.data["detail"]
    assert await _doc_count(db_session, test_clinic.id) == 0


@pytest.mark.asyncio
async def test_title_over_200_chars_is_refused(db_session, test_clinic, test_patient) -> None:
    ctx = await _ctx(db_session, test_clinic.id)

    res = await tool_registry.call(
        ctx,
        TOOL,
        {
            "patient_id": str(test_patient.id),
            "document_type": "referral",
            "title": "x" * 201,
            "content": {"referred_to": "Dr. Ortiz"},
        },
    )

    assert not res.ok
    assert "title" in res.error
    assert await _doc_count(db_session, test_clinic.id) == 0


@pytest.mark.asyncio
async def test_valid_call_generates_with_normalised_content(
    db_session, test_clinic, test_patient
) -> None:
    ctx = await _ctx(db_session, test_clinic.id)

    res = await tool_registry.call(
        ctx,
        TOOL,
        {
            "patient_id": str(test_patient.id),
            "document_type": "medical_certificate",
            "title": "Reposo",
            "content": {"diagnosis": "extraccion", "valid_from": "2026-11-26", "valid_until": ""},
        },
    )

    assert res.ok, res.error
    assert res.data["status"] == "generated"
    doc = await db_session.get(GeneratedDocument, res.data["id"])
    assert doc.content["valid_from"] == "2026-11-26"
    assert "valid_until" not in doc.content
    assert doc.content["recommendations"] == ""


@pytest.mark.asyncio
async def test_unknown_patient_still_reports_not_found(db_session, test_clinic) -> None:
    ctx = await _ctx(db_session, test_clinic.id)

    res = await tool_registry.call(
        ctx,
        TOOL,
        {"patient_id": str(uuid4()), "document_type": "referral", "title": "Ref"},
    )

    assert res.ok
    assert res.data == {"error": "patient_not_found"}
