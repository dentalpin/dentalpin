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


def test_salted_tokens_are_stable_for_one_salt() -> None:
    """Turn-to-turn stability: same salt + value rebuilds the same token."""
    first = Redactor(enabled=True, salt="aa" * 16).table.tokenize("1985-03-14", "DOB")
    second = Redactor(enabled=True, salt="aa" * 16).table.tokenize("1985-03-14", "DOB")
    assert first == second


def test_salted_tokens_differ_across_salts() -> None:
    """Cross-conversation unlinkability (#586)."""
    a = Redactor(enabled=True, salt="aa" * 16).table.tokenize("1985-03-14", "DOB")
    b = Redactor(enabled=True, salt="bb" * 16).table.tokenize("1985-03-14", "DOB")
    assert a != b


def test_salted_token_is_12_hex() -> None:
    import re

    token = Redactor(enabled=True, salt="aa" * 16).table.tokenize("600123123", "PHONE")
    assert re.fullmatch(r"PHONE_[0-9a-f]{12}", token), token


def test_salted_round_trip() -> None:
    r = Redactor(enabled=True, salt="cc" * 16)
    msg = ProviderMessage(
        Role.TOOL,
        [ToolResultBlock("c1", {"full_name": "María González"})],
    )
    token = r.redact_outgoing([msg])[0].content[0].content["full_name"]
    assert token != "María González"
    assert r.rehydrate(token) == "María González"


# --- factory -------------------------------------------------------------


def test_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(LLMConfigError):
        get_provider("not-a-provider")


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


# --- gemini provider -----------------------------------------------------


def test_gemini_provider_requires_key() -> None:
    from app.core.llm.gemini_provider import GeminiProvider

    with pytest.raises(LLMConfigError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key="")


def test_gemini_provider_targets_compat_endpoint() -> None:
    # The whole point of the adapter: the openai SDK pointed at Google's
    # OpenAI-compatible base URL, so the OpenAI wire format is reused as-is.
    from app.core.llm.gemini_provider import (
        GEMINI_OPENAI_COMPAT_BASE_URL,
        GeminiProvider,
    )

    provider = GeminiProvider(api_key="test-key")
    assert str(provider._client.base_url) == GEMINI_OPENAI_COMPAT_BASE_URL


def test_gemini_spec_shape() -> None:
    from app.config import settings
    from app.core.llm.factory import GEMINI_SPEC
    from app.core.llm.gemini_provider import GeminiProvider
    from app.core.llm.spec import ProviderConfig

    assert GEMINI_SPEC.name == "gemini"
    assert GEMINI_SPEC.tool_dialect == "openai"
    assert GEMINI_SPEC.api_key_setting == "GEMINI_API_KEY"
    assert GEMINI_SPEC.default_model == settings.COPILOT_MODEL_CHAT_GEMINI
    provider = GEMINI_SPEC.factory(ProviderConfig(api_key="test-key"))
    assert isinstance(provider, GeminiProvider)


# --- openrouter + groq providers -------------------------------------------


def test_openrouter_provider_requires_key() -> None:
    from app.core.llm.openrouter_provider import OpenRouterProvider

    with pytest.raises(LLMConfigError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key="")


def test_groq_provider_requires_key() -> None:
    from app.core.llm.groq_provider import GroqProvider

    with pytest.raises(LLMConfigError, match="GROQ_API_KEY"):
        GroqProvider(api_key="")


def test_openrouter_provider_targets_compat_endpoint() -> None:
    from app.core.llm.openrouter_provider import (
        OPENROUTER_BASE_URL,
        OpenRouterProvider,
    )

    provider = OpenRouterProvider(api_key="test-key")
    assert str(provider._client.base_url) == OPENROUTER_BASE_URL


def test_groq_provider_targets_compat_endpoint() -> None:
    from app.core.llm.groq_provider import GROQ_OPENAI_COMPAT_BASE_URL, GroqProvider

    provider = GroqProvider(api_key="test-key")
    assert str(provider._client.base_url) == GROQ_OPENAI_COMPAT_BASE_URL


def test_openrouter_groq_spec_shape() -> None:
    from app.config import settings
    from app.core.llm.factory import GROQ_SPEC, OPENROUTER_SPEC
    from app.core.llm.groq_provider import GroqProvider
    from app.core.llm.openrouter_provider import OpenRouterProvider
    from app.core.llm.spec import ProviderConfig

    for spec, cls, key, model in (
        (
            OPENROUTER_SPEC,
            OpenRouterProvider,
            "OPENROUTER_API_KEY",
            settings.COPILOT_MODEL_CHAT_OPENROUTER,
        ),
        (
            GROQ_SPEC,
            GroqProvider,
            "GROQ_API_KEY",
            settings.COPILOT_MODEL_CHAT_GROQ,
        ),
    ):
        assert spec.tool_dialect == "openai"
        assert spec.api_key_setting == key
        assert spec.default_model == model
        assert isinstance(spec.factory(ProviderConfig(api_key="test-key")), cls)


# --- ollama provider --------------------------------------------------------


def test_ollama_provider_needs_no_key() -> None:
    from app.core.llm.ollama_provider import OLLAMA_PLACEHOLDER_API_KEY, OllamaProvider

    provider = OllamaProvider()
    assert str(provider._client.base_url) == "http://ollama:11434/v1/"
    assert provider._client.api_key == OLLAMA_PLACEHOLDER_API_KEY


def test_ollama_provider_targets_configured_endpoint() -> None:
    from app.core.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider(base_url="http://192.168.1.20:11434")
    assert str(provider._client.base_url) == "http://192.168.1.20:11434/v1/"


def test_ollama_provider_strips_trailing_slash() -> None:
    from app.core.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider(base_url="http://ollama:11434/")
    assert str(provider._client.base_url) == "http://ollama:11434/v1/"


def test_ollama_provider_accepts_full_compat_url() -> None:
    from app.core.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider(base_url="http://host.docker.internal:11434/v1")
    assert str(provider._client.base_url) == "http://host.docker.internal:11434/v1/"


def test_ollama_provider_accepts_full_compat_url_with_trailing_slash() -> None:
    from app.core.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider(base_url="http://192.168.1.20:11434/v1/")
    assert str(provider._client.base_url) == "http://192.168.1.20:11434/v1/"


def test_ollama_provider_empty_base_url_uses_default() -> None:
    from app.core.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider(base_url="")
    assert str(provider._client.base_url) == "http://ollama:11434/v1/"


def test_ollama_provider_whitespace_base_url_uses_default() -> None:
    from app.core.llm.ollama_provider import OllamaProvider

    provider = OllamaProvider(base_url="   ")
    assert str(provider._client.base_url) == "http://ollama:11434/v1/"


def test_ollama_spec_shape() -> None:
    from app.config import Settings, settings
    from app.core.llm.factory import OLLAMA_SPEC
    from app.core.llm.ollama_provider import OLLAMA_DEFAULT_BASE_URL, OllamaProvider
    from app.core.llm.spec import ProviderConfig

    assert OLLAMA_SPEC.name == "ollama"
    assert OLLAMA_SPEC.tool_dialect == "openai"
    assert OLLAMA_SPEC.needs_api_key is False
    assert OLLAMA_SPEC.api_key_setting is None
    assert OLLAMA_SPEC.base_url_setting == "OLLAMA_BASE_URL"
    assert OLLAMA_SPEC.default_model == settings.COPILOT_MODEL_CHAT_OLLAMA
    # The provider's fallback default must track the deployment setting's
    # default, or a config edit silently diverges from direct construction.
    # Assert the *field default*, not the ambient value: an operator who
    # sets OLLAMA_BASE_URL (as the prod compose comment invites) must not
    # turn this suite red.
    assert OLLAMA_DEFAULT_BASE_URL == Settings.model_fields["OLLAMA_BASE_URL"].default
    assert isinstance(OLLAMA_SPEC.factory(ProviderConfig(api_key=None)), OllamaProvider)


def test_factory_normalizes_blank_base_url_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.core.llm.factory import OLLAMA_SPEC, get_configured_base_url

    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "")
    assert get_configured_base_url(OLLAMA_SPEC) is None
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "   ")
    assert get_configured_base_url(OLLAMA_SPEC) is None
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://192.168.1.20:11434")
    assert get_configured_base_url(OLLAMA_SPEC) == "http://192.168.1.20:11434"


def test_get_provider_ollama_threads_configured_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.core.llm.factory import OLLAMA_SPEC, get_provider
    from app.core.llm.registry import llm_provider_registry

    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://192.168.1.20:11434")
    previous = llm_provider_registry.get("ollama")
    llm_provider_registry.register(OLLAMA_SPEC)
    try:
        provider = get_provider("ollama")
        assert str(provider._client.base_url) == "http://192.168.1.20:11434/v1/"
    finally:
        if previous is None:
            llm_provider_registry.unregister("ollama")
        else:
            llm_provider_registry.register(previous)


def test_compose_forwards_ollama_base_url() -> None:
    """A self-hosted endpoint the compose never passes cannot be reached.

    Every deployment compose lists the backend env key-by-key and declares
    no ``env_file``, so a setting absent from ``environment:`` keeps its
    default inside the container (#673), and a selection pointing at an
    unreachable host fails only at first chat. Ollama is self-hosted, so
    local development (``docker-compose.yml``) is its primary deployment.
    """
    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    for compose in ("docker-compose.prod.yml", "docker-compose.yml", "docker-compose.coolify.yml"):
        body = (repo / compose).read_text(encoding="utf-8")
        after = body.split("\n  backend:", 1)[1]
        nxt = re.search(r"^  \S", after, re.M)
        backend = after[: nxt.start()] if nxt else after
        assert re.search(r"^\s+OLLAMA_BASE_URL:\s*\$\{OLLAMA_BASE_URL:-\}", backend, re.M), (
            f"{compose} does not forward OLLAMA_BASE_URL"
        )


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
