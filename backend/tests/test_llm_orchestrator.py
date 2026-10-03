"""Layer A core-engine tests: provider abstraction, redaction, orchestrator.

DB-free: the orchestrator only touches three methods on ``ctx.tools``
(``get`` / ``schemas_for`` / ``call``), so a duck-typed fake registry and
a scripted fake provider exercise the whole loop without Postgres.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.core.agents.context import AgentContext, AgentMode
from app.core.agents.orchestrator import (
    BudgetExceeded,
    ConfirmationRequired,
    Final,
    Token,
    ToolCallFinished,
    ToolCallStarted,
    TurnUsage,
    run_turn,
)
from app.core.agents.redaction import Redactor
from app.core.agents.tools.schema import tool_to_openai_schema
from app.core.agents.tools.tool import Tool, ToolCategory, ToolResult
from app.core.llm.base import (
    Done,
    LLMConfigError,
    ProviderEvent,
    ProviderMessage,
    Role,
    TextBlock,
    TextDelta,
    ToolResultBlock,
    ToolUse,
    Usage,
)
from app.core.llm.factory import get_provider


class _Args(BaseModel):
    q: str = ""


class _FakeRegistry:
    """Implements the ToolRegistry surface the orchestrator uses."""

    def __init__(self, tools: dict[str, Tool]) -> None:
        self._tools = tools
        self.calls: list[tuple[str, dict]] = []

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas_for(self, names: list[str], dialect: str = "openai") -> list[dict]:
        return [tool_to_openai_schema(self._tools[n], n) for n in names]

    async def call(self, ctx, name: str, args: dict) -> ToolResult:
        self.calls.append((name, args))
        return ToolResult(ok=True, data={"echoed": args})


class _FakeProvider:
    """Yields scripted neutral events; one script per ``complete`` call."""

    def __init__(self, scripts: list[list[ProviderEvent]]) -> None:
        self._scripts = list(scripts)
        self.calls: list[dict] = []

    async def complete(self, *, system, messages, tools, model, max_tokens) -> AsyncIterator:
        self.calls.append({"messages": messages, "tools": tools, "system": system})
        for ev in self._scripts.pop(0):
            yield ev


async def _noop(ctx, params):  # tool handler placeholder
    return {}


def _tool(name: str, category: ToolCategory, *, free_text: bool = False) -> Tool:
    return Tool(
        name=name,
        description=f"{name} tool",
        parameters=_Args,
        handler=_noop,
        permissions=[],
        category=category,
        exposes_free_text=free_text,
    )


def _ctx(registry: _FakeRegistry) -> AgentContext:
    return AgentContext(
        agent_id=uuid4(),
        session_id=uuid4(),
        clinic_id=uuid4(),
        mode=AgentMode.AUTONOMOUS,
        permissions=["*"],
        tools=registry,  # type: ignore[arg-type]
        db=None,  # type: ignore[arg-type]
    )


async def _collect(gen) -> list:
    return [ev async for ev in gen]


@pytest.mark.asyncio
async def test_simple_text_turn_yields_final_and_usage() -> None:
    reg = _FakeRegistry({})
    provider = _FakeProvider([[TextDelta("hola "), TextDelta("mundo"), Usage(10, 5), Done("stop")]])
    history = [ProviderMessage(Role.USER, [TextBlock("hi")])]

    events = await _collect(
        run_turn(
            ctx=_ctx(reg),
            provider=provider,
            system="s",
            history=history,
            tool_names=[],
            redactor=Redactor(enabled=False),
            model="gpt-4.1",
        )
    )

    tokens = [e for e in events if isinstance(e, Token)]
    assert "".join(t.text for t in tokens) == "hola mundo"
    assert any(isinstance(e, TurnUsage) and e.input_tokens == 10 for e in events)
    assert isinstance(events[-1], Final)
    # assistant turn appended in real space
    assert history[-1].role is Role.ASSISTANT


@pytest.mark.asyncio
async def test_turn_bound_fails_closed_without_budget() -> None:
    """An endless tool loop ends in BudgetExceeded, not a hang (#536)."""
    reg = _FakeRegistry({"m.echo": _tool("echo", ToolCategory.READ)})
    scripts = [[ToolUse(f"t{i}", "m.echo", {}), Done("tool_calls")] for i in range(4)]
    provider = _FakeProvider(scripts)
    history = [ProviderMessage(Role.USER, [TextBlock("hi")])]

    events = await _collect(
        run_turn(
            ctx=_ctx(reg),
            provider=provider,
            system="s",
            history=history,
            tool_names=["m.echo"],
            redactor=Redactor(enabled=False),
            model="gpt-4.1",
            budget=None,
            max_iterations=3,
        )
    )

    assert len(provider.calls) == 3
    assert isinstance(events[-1], BudgetExceeded)
    assert not any(isinstance(e, Final) for e in events)


@pytest.mark.asyncio
async def test_read_tool_executes_then_answers() -> None:
    reg = _FakeRegistry({"m.echo": _tool("echo", ToolCategory.READ)})
    provider = _FakeProvider(
        [
            [ToolUse("c1", "m.echo", {"q": "x"}), Done("tool_calls")],
            [TextDelta("listo"), Done("stop")],
        ]
    )
    history = [ProviderMessage(Role.USER, [TextBlock("haz x")])]

    events = await _collect(
        run_turn(
            ctx=_ctx(reg),
            provider=provider,
            system="s",
            history=history,
            tool_names=["m.echo"],
            redactor=Redactor(enabled=False),
            model="gpt-4.1",
        )
    )

    assert reg.calls == [("m.echo", {"q": "x"})]
    assert any(isinstance(e, ToolCallStarted) for e in events)
    assert any(isinstance(e, ToolCallFinished) and e.ok for e in events)
    assert isinstance(events[-1], Final)


@pytest.mark.asyncio
async def test_write_tool_suspends_without_executing() -> None:
    reg = _FakeRegistry({"m.book": _tool("book", ToolCategory.WRITE)})
    provider = _FakeProvider([[ToolUse("c2", "m.book", {"q": "mañana"}), Done("tool_calls")]])
    history = [ProviderMessage(Role.USER, [TextBlock("agenda")])]

    events = await _collect(
        run_turn(
            ctx=_ctx(reg),
            provider=provider,
            system="s",
            history=history,
            tool_names=["m.book"],
            redactor=Redactor(enabled=False),
            model="gpt-4.1",
        )
    )

    assert reg.calls == []  # never executed
    assert isinstance(events[-1], ConfirmationRequired)
    assert events[-1].name == "m.book"
    # pending tool_use persisted on the assistant message
    assert history[-1].role is Role.ASSISTANT


@pytest.mark.asyncio
async def test_free_text_tool_excluded_under_redaction() -> None:
    reg = _FakeRegistry(
        {
            "m.read": _tool("read", ToolCategory.READ),
            "m.summary": _tool("summary", ToolCategory.READ, free_text=True),
        }
    )
    provider = _FakeProvider([[TextDelta("ok"), Done("stop")]])
    history = [ProviderMessage(Role.USER, [TextBlock("hi")])]

    await _collect(
        run_turn(
            ctx=_ctx(reg),
            provider=provider,
            system="s",
            history=history,
            tool_names=["m.read", "m.summary"],
            redactor=Redactor(enabled=True),
            model="gpt-4.1",
        )
    )

    offered = {t["function"]["name"] for t in provider.calls[0]["tools"]}
    assert offered == {"m.read"}  # free-text tool dropped from cloud path


@pytest.mark.asyncio
async def test_budget_exceeded_short_circuits() -> None:
    class _Broke:
        def check(self) -> bool:
            return False

        def record(self, i: int, o: int) -> None:
            pass

    reg = _FakeRegistry({})
    provider = _FakeProvider([[TextDelta("never"), Done("stop")]])
    history = [ProviderMessage(Role.USER, [TextBlock("hi")])]

    events = await _collect(
        run_turn(
            ctx=_ctx(reg),
            provider=provider,
            system="s",
            history=history,
            tool_names=[],
            redactor=Redactor(enabled=False),
            model="gpt-4.1",
            budget=_Broke(),
        )
    )

    assert len(events) == 1 and isinstance(events[0], BudgetExceeded)
    assert provider.calls == []  # provider never invoked


# --- redaction unit ------------------------------------------------------


def test_redactor_tokenizes_and_restores() -> None:
    r = Redactor(enabled=True)
    msg = ProviderMessage(
        Role.TOOL,
        [ToolResultBlock("c1", {"full_name": "María González", "phone": "600123123"})],
    )
    out = r.redact_outgoing([msg])
    block = out[0].content[0]
    assert block.content["full_name"] != "María González"
    assert block.content["phone"] != "600123123"
    # deterministic + reversible
    token = block.content["full_name"]
    assert r.rehydrate(token) == "María González"
    assert r.resolve_args({"who": token}) == {"who": "María González"}


def test_redactor_disabled_is_identity() -> None:
    r = Redactor(enabled=False)
    msg = ProviderMessage(Role.TOOL, [ToolResultBlock("c1", {"full_name": "Ana"})])
    assert r.redact_outgoing([msg]) is not None
    assert r.redact_outgoing([msg])[0].content[0].content == {"full_name": "Ana"}


def test_redactor_replaces_known_entity_in_free_text() -> None:
    r = Redactor(enabled=True)
    token = r.table.tokenize("María González", "NAME")
    redacted = r.redact_outgoing(
        [ProviderMessage(Role.USER, [TextBlock("agenda a María González")])]
    )
    assert token in redacted[0].content[0].text
    assert "María González" not in redacted[0].content[0].text


def test_redactor_tokenizes_date_of_birth() -> None:
    # get_patient returns date_of_birth as a date; the registry jsonifies
    # it to an ISO string before the redactor sees it (#534).
    from datetime import date

    from app.core.agents.tooling import jsonify

    r = Redactor(enabled=True)
    msg = ProviderMessage(
        Role.TOOL,
        [
            ToolResultBlock(
                "c1",
                jsonify(
                    {
                        "date_of_birth": date(1985, 3, 14),
                        "dob": date(1990, 1, 2),
                        "birth_date": date(2001, 12, 31),
                    }
                ),
            )
        ],
    )
    content = r.redact_outgoing([msg])[0].content[0].content
    for key in ("date_of_birth", "dob", "birth_date"):
        assert isinstance(content[key], str) and content[key].startswith("DOB_"), key
    assert r.rehydrate(content["date_of_birth"]) == "1985-03-14"


# --- factory -------------------------------------------------------------


def test_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(LLMConfigError):
        get_provider("gemini")


def test_openai_name_roundtrip() -> None:
    # OpenAI rejects dots in function names; the provider maps . <-> -.
    from app.core.llm.openai_provider import _from_openai_name, _to_openai_name

    for qualified in ("patients.search_patients", "agenda.get_day_overview"):
        safe = _to_openai_name(qualified)
        assert "." not in safe
        assert _from_openai_name(safe) == qualified


def test_openai_provider_requires_key() -> None:
    # The factory falls back to settings.OPENAI_API_KEY, so test the
    # provider's own guard directly with no key available.
    from app.core.llm.openai_provider import OpenAIProvider

    with pytest.raises(LLMConfigError):
        OpenAIProvider(api_key="")


# --- anthropic provider --------------------------------------------------


def test_anthropic_name_roundtrip() -> None:
    # Anthropic rejects dots in tool names; the provider maps . <-> -.
    from app.core.llm.anthropic_provider import _from_anthropic_name, _to_anthropic_name

    for qualified in ("patients.search_patients", "agenda.get_day_overview"):
        safe = _to_anthropic_name(qualified)
        assert "." not in safe
        assert _from_anthropic_name(safe) == qualified


def test_anthropic_provider_requires_key() -> None:
    from app.core.llm.anthropic_provider import AnthropicProvider

    with pytest.raises(LLMConfigError):
        AnthropicProvider(api_key="")


def test_anthropic_message_mapping_merges_tool_results_into_user_turn() -> None:
    from app.core.llm.anthropic_provider import _to_anthropic_messages
    from app.core.llm.base import ToolUseBlock

    wire = _to_anthropic_messages(
        [
            ProviderMessage(Role.USER, [TextBlock("busca a ana")]),
            ProviderMessage(
                Role.ASSISTANT,
                [
                    TextBlock("Buscando…"),
                    ToolUseBlock("toolu_1", "patients.search_patients", {"q": "ana"}),
                ],
            ),
            ProviderMessage(Role.TOOL, [ToolResultBlock("toolu_1", {"hits": 2}, is_error=False)]),
            ProviderMessage(Role.USER, [TextBlock("y su teléfono?")]),
        ]
    )

    assert [m["role"] for m in wire] == ["user", "assistant", "user"]
    tool_use = wire[1]["content"][1]
    assert tool_use["type"] == "tool_use"
    assert tool_use["name"] == "patients-search_patients"
    # The tool_result turn and the follow-up user text merge into one
    # user message, tool_result blocks first.
    merged = wire[2]["content"]
    assert merged[0]["type"] == "tool_result"
    assert merged[0]["tool_use_id"] == "toolu_1"
    assert "is_error" not in merged[0]
    assert merged[1] == {"type": "text", "text": "y su teléfono?"}


def test_anthropic_message_mapping_flags_error_results() -> None:
    from app.core.llm.anthropic_provider import _to_anthropic_messages

    wire = _to_anthropic_messages(
        [ProviderMessage(Role.TOOL, [ToolResultBlock("toolu_9", {"error": "boom"}, is_error=True)])]
    )
    assert wire[0]["content"][0]["is_error"] is True


@pytest.mark.asyncio
async def test_anthropic_stream_maps_events_to_neutral_types() -> None:
    from types import SimpleNamespace

    from app.core.llm.anthropic_provider import AnthropicProvider

    ns = SimpleNamespace

    events = [
        ns(type="message_start", message=ns(usage=ns(input_tokens=12))),
        ns(type="content_block_start", index=0, content_block=ns(type="text")),
        ns(type="content_block_delta", index=0, delta=ns(type="text_delta", text="Hola")),
        ns(type="content_block_stop", index=0),
        ns(
            type="content_block_start",
            index=1,
            content_block=ns(type="tool_use", id="toolu_1", name="patients-search_patients"),
        ),
        ns(
            type="content_block_delta",
            index=1,
            delta=ns(type="input_json_delta", partial_json='{"q":'),
        ),
        ns(
            type="content_block_delta",
            index=1,
            delta=ns(type="input_json_delta", partial_json='"ana"}'),
        ),
        ns(type="content_block_stop", index=1),
        ns(type="message_delta", delta=ns(stop_reason="tool_use"), usage=ns(output_tokens=7)),
        ns(type="message_stop"),
    ]

    async def _stream():
        for ev in events:
            yield ev

    class _Messages:
        async def create(self, **kwargs):
            return _stream()

    # Bypass __init__ so the test needs neither an API key nor the SDK.
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._client = ns(messages=_Messages())

    out = []
    async for ev in provider.complete(
        system="sys",
        messages=[ProviderMessage(Role.USER, [TextBlock("hola")])],
        tools=[],
        model="claude-sonnet-5",
        max_tokens=64,
    ):
        out.append(ev)

    assert out[0] == TextDelta(text="Hola")
    assert out[1] == Usage(input_tokens=12, output_tokens=7)
    assert out[2] == ToolUse(id="toolu_1", name="patients.search_patients", input={"q": "ana"})
    assert out[3] == Done(stop_reason="tool_use")
