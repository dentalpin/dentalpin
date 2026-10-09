"""copilot round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the copilot tables
and leave every other module untouched, including the core tables its
first revision ``depends_on`` (#552). The branch ships five revisions,
so the downgrade walks ``copilot@-1`` until the tables are gone (never
``@base``: in the merged multi-head graph it resolves to the
whole-graph base).
Marked ``alembic_roundtrip`` and excluded from the default pytest run.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from app.config import settings
from tests.modules._roundtrip_depends import dependent_tables

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

COPILOT_TABLES = {
    "copilot_settings",
    "copilot_conversations",
    "copilot_messages",
    "copilot_nudges",
}
COPILOT_HEAD = "cop_0005"


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=BACKEND_ROOT,
        check=True,
    )


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _list_tables_async() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def _list_tables() -> set[str]:
    return asyncio.run(_list_tables_async())


def test_copilot_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert COPILOT_TABLES.issubset(before), "copilot tables missing after upgrade"

    expected_gone = COPILOT_TABLES | dependent_tables(COPILOT_HEAD)
    baseline = before - expected_gone

    for _ in range(10):
        _alembic("downgrade", "copilot@-1")
        after_down = _list_tables()
        if COPILOT_TABLES.isdisjoint(after_down):
            break
    else:
        raise AssertionError(
            f"copilot tables survived full downgrade: {COPILOT_TABLES & _list_tables()}"
        )
    assert baseline <= after_down, (
        f"downgrade leaked beyond copilot branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert COPILOT_TABLES.issubset(after_up), "copilot tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
