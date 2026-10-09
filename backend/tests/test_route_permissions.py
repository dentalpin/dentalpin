"""Every ``require_permission("...")`` names a permission that exists.

The tool registry already has this guard
(``test_agents_tooling.py::test_every_tool_permission_exists``), with the
reason in its docstring: a permission the system does not know "would
otherwise silently always-deny". Routes gate on the same strings and had
no equivalent check, even though the consequence is worse — a tool that
always denies surfaces as a failed agent call, while a route that always
denies is a 403 for every user forever, with nothing logged anywhere to
say the string was the problem.

The tree is clean today: 673 literal call sites, 189 distinct strings,
all valid. This is here so a typo in the 674th fails in CI instead of in
a clinic.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.core.auth.permissions import CORE_PERMISSIONS
from app.core.plugins.loader import register_discovered

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _known_permissions() -> set[str]:
    """Every namespaced permission a role could hold.

    Built from *discovered* modules rather than
    ``module_registry.get_all_permissions()``, which covers only the
    active (mounted) ones — under pytest almost nothing is mounted, and
    using it here would make this test report every module permission as
    missing.
    """
    known = set(CORE_PERMISSIONS)
    for module in register_discovered():
        for perm in module.get_permissions():
            known.add(f"{module.name}.{perm}")
    return known


def _route_permission_sites() -> dict[str, list[str]]:
    """``{permission: ["path:line", ...]}`` for literal call sites."""
    sites: dict[str, list[str]] = {}
    for path in sorted(APP_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "require_permission"
                and node.args
            ):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                rel = path.relative_to(APP_ROOT.parent)
                sites.setdefault(first.value, []).append(f"{rel}:{first.lineno}")
    return sites


def test_every_route_permission_exists() -> None:
    known = _known_permissions()
    # Sanity-check the universe before trusting a negative result. An
    # empty or tiny `known` would make every route look broken; that is
    # exactly the false positive this assertion exists to prevent (my
    # first pass at this reported 180 missing permissions because the
    # set had 10 entries in it).
    assert len(known) > 100, f"permission universe looks wrong: {len(known)} entries"

    sites = _route_permission_sites()
    assert sites, "found no require_permission call sites — the scan is broken"

    offenders = [
        f"{perm!r} gated at {', '.join(where[:3])}"
        for perm, where in sorted(sites.items())
        if perm not in known
    ]
    assert not offenders, "\n".join(["routes gate on permissions no role can hold:", *offenders])


def test_no_route_gates_on_a_wildcard() -> None:
    """Wildcards belong in grants, not in gates.

    ``permission_matches`` expands ``module.*`` on the *granting* side.
    A route demanding ``billing.*`` would read as "hold every billing
    permission", which is never what an endpoint means and would be a
    silent over-restriction.
    """
    wildcards = {perm: where for perm, where in _route_permission_sites().items() if "*" in perm}
    assert not wildcards, f"wildcard permissions in route gates: {wildcards}"
