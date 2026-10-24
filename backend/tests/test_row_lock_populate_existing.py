"""Every ``SELECT <entity> … FOR UPDATE`` must re-read the row it locks.

A locking select returns the session's cached instance when the row is
already in the identity map, and keeps that instance's attributes as they
were first loaded. The lock is taken, but the code then works on values
read before the lock: a stale series counter hands out a duplicate invoice
number, a stale chain head forks the Verifactu hash chain, a stale stock
quantity loses an adjustment. ``populate_existing`` makes the locked select
overwrite the cached attributes with the locked row.

Locks on a bare column (``select(Model.id)``) only serialise and read
nothing, so they are exempt.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _chain(node: ast.AST) -> list[ast.Call]:
    """The calls of a method chain, outermost first."""
    calls = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        calls.append(node)
        node = node.func.value
    if isinstance(node, ast.Call):
        calls.append(node)
    return calls


def _selects_entity(select_call: ast.Call) -> bool:
    # select(Model) locks an entity; select(Model.id) / select(func…) do not.
    return any(isinstance(arg, ast.Name) for arg in select_call.args)


def _offenders() -> list[str]:
    found = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        seen: set[int] = set()
        for node in ast.walk(tree):
            if id(node) in seen or not isinstance(node, ast.Call):
                continue
            calls = _chain(node)
            for c in calls:
                seen.add(id(c))
            names = [
                c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")
                for c in calls
            ]
            if "with_for_update" not in names or names[-1] != "select":
                continue
            if not _selects_entity(calls[-1]):
                continue
            populates = any(
                n == "execution_options"
                and any(
                    kw.arg == "populate_existing"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                    for kw in c.keywords
                )
                for n, c in zip(names, calls, strict=True)
            )
            if not populates:
                found.append(f"{path.relative_to(APP.parent)}:{node.lineno}")
    return found


def test_every_entity_row_lock_rereads_the_row():
    assert _offenders() == [], (
        "SELECT … FOR UPDATE on an entity without "
        ".execution_options(populate_existing=True) — the lock returns the "
        "cached instance with pre-lock values:\n" + "\n".join(_offenders())
    )
