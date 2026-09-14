"""Layer C: copilot orchestrator bridge against a live DB + fake provider.

Validates persistence, the inline-confirm suspend, and resume-executes —
the conversation-state machine that backs the chat surface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.models import Agent, AgentSession
from app.core.agents.orchestrator import ConfirmationRequired, Final, Token, ToolCallFinished
from app.core.auth.models import User
from app.core.llm.base import Done, ProviderEvent, TextDelta, ToolUse, Usage
from app.core.llm.factory import ANTHROPIC_SPEC
from app.core.llm.registry import llm_provider_registry
from app.modules.copilot.bridge import _dialect_for, _tool_names_for, drive_turn, resume_turn
from app.modules.copilot.models import CopilotMessage
from app.modules.copilot.service import ConversationService, CopilotSettingsService
from app.modules.patients.models import Patient


class _FakeProvider:
    def __init__(self, scripts: list[list[ProviderEvent]]) -> None:
        self._scripts = list(scripts)

    async def complete(self, *, system, messages, tools, model, max_tokens) -> AsyncIterator:
        for ev in self._scripts.pop(0):
            yield ev


async def _setup(db: AsyncSession, clinic_id):
    user_id = await db.scalar(select(User.id).limit(1))
    agent = Agent(clinic_id=clinic_id, name="Copilot", type="copilot", mode="autonomous", config={})
    db.add(agent)
    await db.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=clinic_id, supervisor_id=user_id)
    db.add(session)
    await db.flush()
    settings_row = await CopilotSettingsService.get_or_create(db, clinic_id)
    conv = await ConversationService.create(
        db,
        clinic_id=clinic_id,
        user_id=user_id,
        provider="openai",
        model="gpt-4o-mini",
        session_id=session.id,
    )
    return conv, settings_row, user_id, agent.id, session.id


async def _drive(db, conv, settings_row, user_id, agent_id, session_id, provider, text="hola"):
    perms = ["*"]
    return [
        ev
        async for ev in drive_turn(
            db=db,
            conv=conv,
            settings_row=settings_row,
            permissions=perms,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            user_text=text,
            provider=provider,
        )
    ]


async def _count_messages(db, conv_id) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(CopilotMessage)
            .where(CopilotMessage.conversation_id == conv_id)
        )
    )


def test_tool_names_respect_permissions() -> None:
    read_only = _tool_names_for(["patients.read"])
    assert "patients.search_patients" in read_only
    assert "patients.create_patient" not in read_only  # WRITE needs patients.write


def test_tool_dialect_comes_from_registered_provider_spec() -> None:
    spec = replace(ANTHROPIC_SPEC, name="registry-dialect-test")
    llm_provider_registry.register(spec)
    try:
        assert _dialect_for(spec.name) == "anthropic"
    finally:
        llm_provider_registry.unregister(spec.name)


def test_system_prompt_keeps_offbooks_rule_and_playbooks() -> None:
    """The playbook refactor must never drop the off-books sentence."""
    from app.modules.copilot.bridge import SYSTEM_PROMPT

    assert "ejes contables separados" in SYSTEM_PROMPT
    assert "NUNCA" in SYSTEM_PROMPT
    # Playbooks present.
    assert "Briefing del día" in SYSTEM_PROMPT
    assert "Cubrir un hueco" in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_text_turn_persists_messages(db_session, test_clinic) -> None:
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
    provider = _FakeProvider([[TextDelta("Hola, ¿en qué ayudo?"), Usage(8, 5), Done("stop")]])

    events = await _drive(db_session, conv, settings_row, user_id, agent_id, session_id, provider)

    assert any(isinstance(e, Token) for e in events)
    assert isinstance(events[-1], Final)
    assert await _count_messages(db_session, conv.id) == 2  # user + assistant
    assert conv.total_input_tokens == 8 and conv.total_output_tokens == 5


@pytest.mark.asyncio
async def test_briefing_playbook_chains_read_tools(db_session, test_clinic) -> None:
    """Multi-tool READ chain (the daily-briefing playbook shape) terminates."""
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
    provider = _FakeProvider(
        [
            [ToolUse("t1", "agenda.get_day_overview", {"date": "2030-06-01"}), Done("tool_calls")],
            [ToolUse("t2", "recalls.list_due_recalls", {"overdue": True}), Done("tool_calls")],
            [
                ToolUse("t3", "budget.list_budgets", {"status": ["sent"]}),
                Done("tool_calls"),
            ],
            [TextDelta("Briefing: sin citas, sin rellamadas, sin presupuestos."), Done("stop")],
        ]
    )
    events = await _drive(
        db_session, conv, settings_row, user_id, agent_id, session_id, provider, "briefing del día"
    )
    finished = [e for e in events if isinstance(e, ToolCallFinished)]
    assert [f.name for f in finished] == [
        "agenda.get_day_overview",
        "recalls.list_due_recalls",
        "budget.list_budgets",
    ]
    assert all(f.ok for f in finished)
    assert isinstance(events[-1], Final)


@pytest.mark.asyncio
async def test_write_suspends_then_resume_executes(db_session, test_clinic) -> None:
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)

    # Turn 1: model asks to create a patient (WRITE) → suspend, no insert.
    p1 = _FakeProvider(
        [
            [
                ToolUse(
                    "c1",
                    "patients.create_patient",
                    {"first_name": "María", "last_name": "González"},
                ),
                Done("tool_calls"),
            ]
        ]
    )
    events = await _drive(
        db_session, conv, settings_row, user_id, agent_id, session_id, p1, "crea a María"
    )
    assert isinstance(events[-1], ConfirmationRequired)
    assert events[-1].name == "patients.create_patient"

    created = await db_session.scalar(
        select(func.count()).select_from(Patient).where(Patient.clinic_id == test_clinic.id)
    )
    assert created == 0  # not executed yet

    # Turn 2: user confirms → tool executes, model wraps up.
    p2 = _FakeProvider([[TextDelta("Hecho, paciente creada."), Done("stop")]])
    resumed = [
        ev
        async for ev in resume_turn(
            db=db_session,
            conv=conv,
            settings_row=settings_row,
            permissions=["*"],
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            call_id="c1",
            approve=True,
            provider=p2,
        )
    ]
    assert any(isinstance(e, ToolCallFinished) and e.ok for e in resumed)
    assert isinstance(resumed[-1], Final)

    now_created = await db_session.scalar(
        select(func.count())
        .select_from(Patient)
        .where(Patient.clinic_id == test_clinic.id, Patient.first_name == "María")
    )
    assert now_created == 1  # executed on confirm


@pytest.mark.asyncio
async def test_reject_does_not_execute(db_session, test_clinic) -> None:
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
    p1 = _FakeProvider(
        [
            [
                ToolUse(
                    "c9", "patients.create_patient", {"first_name": "Ana", "last_name": "Ruiz"}
                ),
                Done("tool_calls"),
            ]
        ]
    )
    await _drive(db_session, conv, settings_row, user_id, agent_id, session_id, p1, "crea a Ana")

    p2 = _FakeProvider([[TextDelta("Cancelado."), Done("stop")]])
    [
        ev
        async for ev in resume_turn(
            db=db_session,
            conv=conv,
            settings_row=settings_row,
            permissions=["*"],
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            call_id="c9",
            approve=False,
            provider=p2,
        )
    ]
    count = await db_session.scalar(
        select(func.count()).select_from(Patient).where(Patient.first_name == "Ana")
    )
    assert count == 0  # rejected → never created
