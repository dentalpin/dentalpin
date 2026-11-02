"""Calendar dates come from the clinic's day, never the server's.

The server runs on UTC. ``date.today()`` and ``datetime.now(UTC).date()``
(or ``.year`` / ``.month``) are the UTC day, which differs from the
clinic's for hours every day: from 18:00 in a UTC-6 clinic it is already
tomorrow, so a quote valid until today read as expired. Use
``clinic_today`` / ``clinic_today_for`` from ``app.core.utils.dates``.

The allowlist holds the reviewed exceptions, each with its reason.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

ALLOWED = {
    # The helper itself.
    "app/core/utils/dates.py": "defines clinic_today",
    # Fallbacks behind an explicit ``today`` parameter the callers pass.
    "app/modules/billing/service.py": "`today or date.today()` fallback; create_series default",
    "app/modules/billing/workflow.py": "`issue_date or today or date.today()` fallback",
    # Historic import: defaults for rows the source left undated.
    "app/modules/migration_import/service.py": "import cutoff, not a clinic calendar day",
    "app/modules/migration_import/mappers/professional.py": "import activity window",
    "app/modules/migration_import/mappers/budget.py": "undated source quote",
    "app/modules/migration_import/mappers/recall.py": "undated source recall",
    "app/modules/migration_import/mappers/payment.py": "undated source payment",
    # Usage accounting rolls on the UTC month for every clinic alike.
    "app/modules/copilot/service.py": "LLM usage period, UTC by design",
}


def _is_server_day(node: ast.AST) -> bool:
    # date.today()
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "today"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "date"
    ):
        return True
    # datetime.now() / datetime.now(UTC) followed by .date() / .year / .month.
    # datetime.now(<clinic zone>) is the clinic's day and is fine.
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute) and target.attr in ("date", "year", "month"):
        inner = target.value
        if not (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr in ("now", "utcnow")
            and isinstance(inner.func.value, ast.Name)
            and inner.func.value.id == "datetime"
        ):
            return False
        if not inner.args:
            return True
        zone = inner.args[0]
        return (isinstance(zone, ast.Name) and zone.id == "UTC") or (
            isinstance(zone, ast.Attribute) and zone.attr == "utc"
        )
    return False


def _offenders() -> list[str]:
    found = []
    for path in sorted(APP.rglob("*.py")):
        rel = str(path.relative_to(APP.parent))
        if rel in ALLOWED or "seed" in path.name or path.name == "demo_data.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Call, ast.Attribute)) and _is_server_day(node):
                found.append(f"{rel}:{node.lineno}")
    return sorted(set(found))


def test_no_calendar_day_from_the_server_clock():
    assert _offenders() == [], (
        "Calendar day read from the server (UTC) clock; use clinic_today_for:\n"
        + "\n".join(_offenders())
    )


def test_allowlist_has_no_stale_entries():
    for rel in ALLOWED:
        assert (APP.parent / rel).exists(), f"allowlisted file is gone: {rel}"
