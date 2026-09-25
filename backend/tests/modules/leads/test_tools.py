"""The tool surface must not carry enquirer prose into the cloud path.

``motive`` and ``description`` are typed by anyone on the internet through the
public form. A tool result whose tool is not flagged ``exposes_free_text`` is
sent to the cloud LLM under redaction, so exactly one tool may return that
prose — ``get_lead``, which is flagged — and this file pins that shape.

It is a cheap guard with an expensive failure mode: re-adding a prose field to
``_lead_summary`` would leak it through five tools at once (list, create,
update, convert, and the settings-free paths), and nothing else would notice.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents import AgentContext, AgentMode, tool_registry
from app.core.auth.models import Clinic
from app.modules.leads.models import Lead
from app.modules.leads.service import LeadService
from app.modules.leads.tools import GetLeadArgs, ListLeadsArgs, get_tools

PROSE_KEYS = {"motive", "description"}

# Distinctive strings so a leak is greppable in the serialized result.
MOTIVE = "Cancel my implant surgery"
DESCRIPTION = "I am allergic to penicillin, please note it."


def _ctx(db: AsyncSession, clinic: Clinic) -> AgentContext:
    return AgentContext(
        agent_id=uuid4(),
        session_id=uuid4(),
        clinic_id=clinic.id,
        mode=AgentMode.SUPERVISED,
        permissions=["leads.read", "leads.write"],
        tools=tool_registry,
        db=db,
    )


def _tool(name: str):
    tool = next((t for t in get_tools() if t.name == name), None)
    assert tool is not None, f"{name} is missing from the leads tool set"
    return tool


async def _make_lead(db: AsyncSession, clinic: Clinic) -> Lead:
    return await LeadService.create_lead(
        db,
        clinic.id,
        {
            "full_name": "Marta Ruiz",
            "phone": "+34 600 111 222",
            "email": "marta@example.com",
            "motive": MOTIVE,
            "description": DESCRIPTION,
            "availability_days": ["mon"],
            "availability_slot": "afternoon",
        },
    )


@pytest.mark.asyncio
async def test_list_leads_result_carries_no_enquirer_prose(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The flagged tool is the *only* door the prose leaves by."""
    await _make_lead(db_session, test_clinic)

    result = await _tool("list_leads").handler(_ctx(db_session, test_clinic), ListLeadsArgs())

    assert result["total"] == 1
    row = result["leads"][0]
    assert PROSE_KEYS.isdisjoint(row), sorted(row)
    # Not just absent from the top level: nowhere in the payload.
    assert MOTIVE not in str(result)
    assert DESCRIPTION not in str(result)
    # The identifying fields the agent legitimately needs are still there.
    assert row["full_name"] == "Marta Ruiz"
    assert row["phone"] == "+34 600 111 222"


@pytest.mark.asyncio
async def test_get_lead_returns_the_prose_and_is_flagged_for_it(
    db_session: AsyncSession, test_clinic: Clinic
):
    lead = await _make_lead(db_session, test_clinic)

    tool = _tool("get_lead")
    assert tool.exposes_free_text is True

    result = await tool.handler(_ctx(db_session, test_clinic), GetLeadArgs(lead_id=lead.id))

    assert result["motive"] == MOTIVE
    assert result["description"] == DESCRIPTION


@pytest.mark.asyncio
async def test_exactly_one_tool_is_flagged_as_free_text():
    """Widening the flag would push other tools off the cloud path; dropping it
    from get_lead would push the enquirer's words onto it. Both are silent, so
    the set is pinned."""
    flagged = {tool.name for tool in get_tools() if tool.exposes_free_text}

    assert flagged == {"get_lead"}
