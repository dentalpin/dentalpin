"""Event names are published through ``EventType``, never as a literal.

A publish with a bare string is the quietest bug the event bus can
have: ``event_bus.publish("treatment_plan.treatmnet_added", ...)``
raises nothing, matches no subscriber, and leaves no log line. The
constant turns the same typo into an ``AttributeError`` at import.

It also keeps the wiring greppable. ``treatment_plan`` used to publish
six of its events as literals while every other module used the
constant, and a sweep for "is anything subscribing to an event nobody
publishes?" reported all six as orphans — they were not, but there was
no way to tell without reading each call site.

A non-literal first argument (``publish(specific, ...)`` from a
status -> EventType map, ``publish(_NOTE_TYPE_TO_EVENT[t], ...)``) is
fine and intentionally allowed: the name still comes from a constant,
just one picked at runtime.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def _literal_publishes() -> list[str]:
    offenders: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr in {"publish", "_publish"}):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    offenders.append(
                        f"{path.relative_to(APP.parent)}:{arg.lineno}: "
                        f'publish("{arg.value}") — use the EventType constant'
                    )
                    break
                # First non-dict positional is the event name; stop at it.
                if not isinstance(arg, ast.Dict):
                    break
    return offenders


def test_no_event_is_published_as_a_string_literal() -> None:
    offenders = _literal_publishes()
    assert not offenders, "\n".join(offenders)
