"""Layer C: copilot orchestrator bridge against a live DB + fake provider.

Validates persistence, the inline-confirm suspend, and resume-executes —
the conversation-state machine that backs the chat surface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.agents.models import Agent, AgentSession
from app.core.agents.orchestrator import ConfirmationRequired, Final, Token, ToolCallFinished
from app.core.auth.models import User
from app.core.llm.base import Done, ProviderEvent, TextDelta, ToolUse, Usage
from app.core.llm.factory import ANTHROPIC_SPEC
from app.core.llm.registry import llm_provider_registry
from app.modules.copilot.bridge import (
    SYSTEM_PROMPT,
    _dialect_for,
    _system_prompt,
    _tool_names_for,
    drive_turn,
    resume_turn,
)
from app.modules.copilot.models import CopilotMessage
from app.modules.copilot.service import ConversationService, CopilotSettingsService
from app.modules.patients.models import Patient


class _FakeProvider:
    def __init__(self, scripts: list[list[ProviderEvent]]) -> None:
        self._scripts = list(scripts)
        self.seen_max_tokens: list[int] = []
        self.seen_system: list[str] = []

    async def complete(self, *, system, messages, tools, model, max_tokens) -> AsyncIterator:
        self.seen_max_tokens.append(max_tokens)
        self.seen_system.append(system)
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
@pytest.mark.parametrize(
    ("zone", "server_now", "clinic_day", "clinic_clock"),
    [
        # East of UTC, just before server midnight: the clinic is already tomorrow.
        (
            "Europe/Madrid",
            datetime(2031, 3, 4, 23, 30, tzinfo=UTC),
            "miércoles 2031-03-05",
            "00:30 (zona horaria Europe/Madrid, UTC+01:00)",
        ),
        # West of UTC, just after server midnight: the clinic is still yesterday.
        (
            "America/Mexico_City",
            datetime(2031, 3, 5, 1, 0, tzinfo=UTC),
            "martes 2031-03-04",
            "19:00 (zona horaria America/Mexico_City, UTC-06:00)",
        ),
    ],
)
async def test_system_prompt_states_the_clinic_day_not_the_server_day(
    db_session, test_clinic, zone, server_now, clinic_day, clinic_clock
) -> None:
    """#1104: the model resolves "hoy"/"mañana" from the prompt's date, so it
    must be the clinic's calendar day; the server's UTC day is one off here."""
    test_clinic.timezone = zone
    await db_session.flush()

    prompt = await _system_prompt(db_session, test_clinic.id, now=server_now)

    assert prompt.startswith(SYSTEM_PROMPT)
    assert f"{clinic_day}, {clinic_clock}" in prompt
    assert server_now.date().isoformat() not in prompt


@pytest.mark.asyncio
async def test_both_turn_paths_send_the_clinic_clock(db_session, test_clinic) -> None:
    """drive_turn and resume_turn are two provider calls; both get the
    per-turn prompt, not the bare constant."""
    test_clinic.timezone = "America/Mexico_City"
    await db_session.flush()
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)

    p1 = _FakeProvider(
        [
            [
                ToolUse(
                    "c1", "patients.create_patient", {"first_name": "Ana", "last_name": "Ruiz"}
                ),
                Done("tool_calls"),
            ]
        ]
    )
    events = await _drive(
        db_session, conv, settings_row, user_id, agent_id, session_id, p1, "crea a Ana"
    )
    p2 = _FakeProvider([[TextDelta("Hecho."), Done("stop")]])
    async for _ in resume_turn(
        db=db_session,
        conv=conv,
        settings_row=settings_row,
        permissions=["*"],
        user_id=user_id,
        agent_id=agent_id,
        session_id=session_id,
        call_id=events[-1].call_id,
        approve=True,
        provider=p2,
    ):
        pass

    for system in p1.seen_system + p2.seen_system:
        assert system.startswith(SYSTEM_PROMPT)
        assert "zona horaria America/Mexico_City, UTC-06:00" in system
    assert len(p1.seen_system) == len(p2.seen_system) == 1


@pytest.mark.asyncio
async def test_text_turn_persists_messages(db_session, test_clinic) -> None:
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
    provider = _FakeProvider([[TextDelta("Hola, ¿en qué ayudo?"), Usage(8, 5), Done("stop")]])

    events = await _drive(db_session, conv, settings_row, user_id, agent_id, session_id, provider)

    assert any(isinstance(e, Token) for e in events)
    assert isinstance(events[-1], Final)
    assert await _count_messages(db_session, conv.id) == 2  # user + assistant
    assert conv.total_input_tokens == 8 and conv.total_output_tokens == 5
    assert provider.seen_max_tokens == [app_settings.COPILOT_MAX_TOKENS]


@pytest.mark.asyncio
async def test_bridge_forwards_the_configured_token_ceiling(
    db_session, test_clinic, monkeypatch
) -> None:
    """The bridge must read COPILOT_MAX_TOKENS, not a baked-in literal.

    `drive_turn` and `resume_turn` both hardcoded 4096, so the setting an
    operator could see in config.py changed nothing; a value the default
    never differs from would not notice. Pin it to a value 4096 is not.
    """
    monkeypatch.setattr(app_settings, "COPILOT_MAX_TOKENS", 12345)
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
    provider = _FakeProvider([[TextDelta("ok"), Done("stop")]])

    await _drive(db_session, conv, settings_row, user_id, agent_id, session_id, provider)

    assert provider.seen_max_tokens == [12345]


@pytest.mark.asyncio
async def test_resume_turn_also_forwards_the_configured_token_ceiling(
    db_session, test_clinic, monkeypatch
) -> None:
    """Both call sites, not just drive_turn: the resume path is a second
    provider call and would otherwise keep the old ceiling forever."""
    monkeypatch.setattr(app_settings, "COPILOT_MAX_TOKENS", 54321)
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)

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
    call_id = events[-1].call_id

    p2 = _FakeProvider([[TextDelta("Hecho."), Done("stop")]])
    async for _ in resume_turn(
        db=db_session,
        conv=conv,
        settings_row=settings_row,
        permissions=["*"],
        user_id=user_id,
        agent_id=agent_id,
        session_id=session_id,
        call_id=call_id,
        approve=True,
        provider=p2,
    ):
        pass

    assert p2.seen_max_tokens == [54321]


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
async def test_double_confirm_replays_without_reexecuting(db_session, test_clinic) -> None:
    """A retry/double-click on confirm replays the stored result (#532)."""
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
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

    async def _resume(provider):
        return [
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
                provider=provider,
            )
        ]

    p2 = _FakeProvider([[TextDelta("Hecho."), Done("stop")]])
    first = await _resume(p2)
    assert any(isinstance(e, ToolCallFinished) and e.ok for e in first)

    async def _count_marias() -> int:
        return int(
            await db_session.scalar(
                select(func.count())
                .select_from(Patient)
                .where(Patient.clinic_id == test_clinic.id, Patient.first_name == "María")
            )
        )

    assert await _count_marias() == 1

    # Second confirm of the same call: replayed, not executed.
    p3 = _FakeProvider([[TextDelta("Hecho de nuevo."), Done("stop")]])
    second = await _resume(p3)
    assert any(isinstance(e, ToolCallFinished) and e.ok for e in second)
    assert await _count_marias() == 1


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


class _FailingProvider:
    """A provider whose call fails — a timeout, a rate limit, an outage."""

    async def complete(self, *, system, messages, tools, model, max_tokens) -> AsyncIterator:
        raise RuntimeError("provider timeout")
        yield  # pragma: no cover — makes this an async generator


async def _stream_frames(monkeypatch, db, factory) -> list[tuple[str, dict]]:
    """Run ``factory`` through the router's real SSE wrapper on ``db``.

    ``_stream`` opens its own session; point it at the test session so the
    commit/rollback it does is the one under test.
    """
    import contextlib
    import importlib
    import json

    # ``app.modules.copilot.router`` the attribute is the APIRouter; the
    # module is what holds ``async_session_maker`` and ``_stream``.
    copilot_router = importlib.import_module("app.modules.copilot.router")

    @contextlib.asynccontextmanager
    async def _session():
        yield db

    monkeypatch.setattr(copilot_router, "async_session_maker", _session)
    response = copilot_router._stream(factory)
    frames = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        head, data = text.strip().split("\n", 1)
        frames.append((head.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return frames


@pytest.mark.asyncio
async def test_confirmed_write_survives_a_failing_follow_up_call(
    db_session, test_clinic, monkeypatch
) -> None:
    """#1093: the write the user saw succeed must not be rolled back when
    the model call after it fails, and a retry must not run it again."""
    conv, settings_row, user_id, agent_id, session_id = await _setup(db_session, test_clinic.id)
    conv_id, clinic_id = conv.id, test_clinic.id
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
    await db_session.commit()  # the router commits the suspended turn

    def _resume(provider):
        def factory(db):
            return resume_turn(
                db=db,
                conv=conv,
                settings_row=settings_row,
                permissions=["*"],
                user_id=user_id,
                agent_id=agent_id,
                session_id=session_id,
                call_id="c1",
                approve=True,
                provider=provider,
            )

        return factory

    frames = await _stream_frames(monkeypatch, db_session, _resume(_FailingProvider()))

    # The user is told the write happened, then that the reply failed.
    assert ("tool_result", "c1", True) in [(e, d.get("call_id"), d.get("ok")) for e, d in frames]
    assert frames[-1] == ("error", {"detail": "provider timeout"})

    async def _count_marias() -> int:
        return int(
            await db_session.scalar(
                select(func.count())
                .select_from(Patient)
                .where(Patient.clinic_id == clinic_id, Patient.first_name == "María")
            )
        )

    assert await _count_marias() == 1, "confirmed write was rolled back"
    roles = [
        r
        for (r,) in (
            await db_session.execute(
                select(CopilotMessage.role)
                .where(CopilotMessage.conversation_id == conv_id)
                .order_by(CopilotMessage.seq)
            )
        ).all()
    ]
    assert roles == ["user", "assistant", "tool"]  # tool result kept, no reply

    # Retrying the confirmation replays the stored result (#532).
    conv = await db_session.get(type(conv), conv_id)
    settings_row = await CopilotSettingsService.get_or_create(db_session, clinic_id)
    p3 = _FakeProvider([[TextDelta("Hecho."), Done("stop")]])
    retry = await _stream_frames(monkeypatch, db_session, _resume(p3))
    assert ("tool_result", "c1", True) in [(e, d.get("call_id"), d.get("ok")) for e, d in retry]
    assert retry[-1][0] == "done"
    assert await _count_marias() == 1, "retry executed the write a second time"
