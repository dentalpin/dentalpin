"""Provider-agnostic tool-use loop — the reusable agentic engine.

``run_turn`` drives one user turn: stream the model, execute READ tools
through the registry chokepoint, and — for WRITE/DESTRUCTIVE tools —
**suspend** for inline confirmation instead of executing. It knows
nothing about HTTP, SSE, or the copilot module; surfaces (chat, future
voice) consume its event stream.

Conventions:

* ``history`` is owned by the caller and **mutated in place** — after
  the generator finishes or suspends, ``history`` holds the new
  assistant (and any tool) messages, in **real space**, ready to
  persist. The redactor tokenizes a copy on the way to the provider;
  history itself never holds tokens. Tokens are deterministic, so each
  provider call re-derives the same token for the same value.
* One tool call per assistant turn (the OpenAI provider forces
  ``parallel_tool_calls=False``). A WRITE/DESTRUCTIVE call suspends the
  turn; the surface resumes by appending a tool-result message and
  calling ``run_turn`` again.

See ``docs/technical/copilot-agentic-architecture.md`` §2.2, §6.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.agents.context import AgentContext
from app.core.agents.redaction import Redactor
from app.core.agents.tools.tool import ToolCategory
from app.core.llm.base import (
    Done,
    ProviderMessage,
    Role,
    TextBlock,
    TextDelta,
    ToolResultBlock,
    ToolUse,
    ToolUseBlock,
    Usage,
)

# --- Turn events (what a surface renders) -------------------------------


@dataclass
class Token:
    """An incremental piece of assistant text, rehydrated for display."""

    text: str


@dataclass
class ToolCallStarted:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolCallFinished:
    call_id: str
    name: str
    ok: bool
    result: Any


@dataclass
class ConfirmationRequired:
    """A WRITE/DESTRUCTIVE call awaiting the user's inline confirmation."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TurnUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class Final:
    stop_reason: str


@dataclass
class BudgetExceeded:
    pass


TurnEvent = (
    Token
    | ToolCallStarted
    | ToolCallFinished
    | ConfirmationRequired
    | TurnUsage
    | Final
    | BudgetExceeded
)


class BudgetGuard(Protocol):
    """Per-clinic token/cost ceiling. Surfaces supply a concrete impl."""

    def check(self) -> bool:
        """Return ``True`` while still within budget."""
        ...

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Account the usage of one completed provider call."""
        ...


@dataclass
class _Accumulator:
    text_parts: list[str] = field(default_factory=list)
    tool_uses: list[ToolUse] = field(default_factory=list)
    usage: Usage | None = None
    stop_reason: str = "stop"


def _effective_tools(ctx: AgentContext, tool_names: list[str], redactor: Redactor) -> list[str]:
    """Drop free-text-returning tools from the cloud path under redaction."""
    if not redactor.enabled:
        return tool_names
    out: list[str] = []
    for name in tool_names:
        tool = ctx.tools.get(name)
        if tool is not None and getattr(tool, "exposes_free_text", False):
            continue
        out.append(name)
    return out


#: Hard cap on provider round-trips per turn (#536). Independent of
#: the token budget: with no configured limit nothing else bounds the
#: loop, so exhaustion fails closed with BudgetExceeded.
MAX_TURN_ITERATIONS = 25


async def run_turn(
    *,
    ctx: AgentContext,
    provider: Any,  # app.core.llm.base.Provider (structural)
    system: str,
    history: list[ProviderMessage],
    tool_names: list[str],
    redactor: Redactor,
    model: str,
    max_tokens: int = 4096,
    budget: BudgetGuard | None = None,
    dialect: str = "openai",
    max_iterations: int = MAX_TURN_ITERATIONS,
) -> AsyncIterator[TurnEvent]:
    """Run one user turn to completion, a tool result, or a confirmation."""
    for _ in range(max_iterations):
        if budget is not None and not budget.check():
            yield BudgetExceeded()
            return

        effective = _effective_tools(ctx, tool_names, redactor)
        schemas = ctx.tools.schemas_for(effective, dialect) if effective else []
        outgoing = redactor.redact_outgoing(history)

        acc = _Accumulator()
        # Buffer deltas and only rehydrate/emit at whitespace boundaries: a
        # redaction token (e.g. NAME_6e5659) has no internal spaces, so it
        # is always whole within a flushed segment — per-delta rehydration
        # would miss tokens split across two deltas.
        buf = ""
        async for ev in provider.complete(
            system=system,
            messages=outgoing,
            tools=schemas,
            model=model,
            max_tokens=max_tokens,
        ):
            if isinstance(ev, TextDelta):
                acc.text_parts.append(ev.text)
                buf += ev.text
                cut = max(buf.rfind(" "), buf.rfind("\n"))
                if cut >= 0:
                    seg, buf = buf[: cut + 1], buf[cut + 1 :]
                    yield Token(redactor.rehydrate(seg))
            elif isinstance(ev, ToolUse):
                acc.tool_uses.append(ev)
            elif isinstance(ev, Usage):
                acc.usage = ev
            elif isinstance(ev, Done):
                acc.stop_reason = ev.stop_reason
        if buf:
            yield Token(redactor.rehydrate(buf))

        if acc.usage is not None:
            if budget is not None:
                budget.record(acc.usage.input_tokens, acc.usage.output_tokens)
            yield TurnUsage(acc.usage.input_tokens, acc.usage.output_tokens)

        # Persist the assistant turn in real space (rehydrated text +
        # resolved tool args), so history never carries tokens.
        assistant_blocks: list[Any] = []
        if acc.text_parts:
            assistant_blocks.append(TextBlock(redactor.rehydrate("".join(acc.text_parts))))
        for tu in acc.tool_uses:
            assistant_blocks.append(ToolUseBlock(tu.id, tu.name, redactor.resolve_args(tu.input)))
        history.append(ProviderMessage(role=Role.ASSISTANT, content=assistant_blocks))

        if not acc.tool_uses:
            yield Final(stop_reason=acc.stop_reason)
            return

        tu = acc.tool_uses[0]
        real_args = redactor.resolve_args(tu.input)
        tool = ctx.tools.get(tu.name)

        if tool is None:
            history.append(
                ProviderMessage(
                    role=Role.TOOL,
                    content=[
                        ToolResultBlock(tu.id, {"error": f"unknown tool: {tu.name}"}, is_error=True)
                    ],
                )
            )
            continue

        if tool.category is ToolCategory.READ:
            yield ToolCallStarted(tu.id, tu.name, real_args)
            res = await ctx.tools.call(ctx, tu.name, real_args)
            payload: Any = res.data if res.ok else {"error": res.error}
            history.append(
                ProviderMessage(
                    role=Role.TOOL,
                    content=[ToolResultBlock(tu.id, payload, is_error=not res.ok)],
                )
            )
            yield ToolCallFinished(tu.id, tu.name, res.ok, payload)
            continue

        # WRITE / DESTRUCTIVE: do not execute. Suspend for inline confirm.
        # The assistant message (with this tool_use) is already in history.
        yield ConfirmationRequired(tu.id, tu.name, real_args)
        return

    yield BudgetExceeded()
