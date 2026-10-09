"""recall_reminders round-trip uninstall test.

Install -> uninstall -> reinstall must drop nothing but also leak
nothing: the module ships a single noop migration, so its table set is
empty and the test proves the uninstall path is a safe no-op that
leaves every other module untouched (#552).
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

RECALL_REMINDERS_TABLES: set[str] = set()
RECALL_REMINDERS_HEAD = "rr_0001"


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


def test_recall_reminders_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()

    expected_gone = RECALL_REMINDERS_TABLES | dependent_tables(RECALL_REMINDERS_HEAD)
    baseline = before - expected_gone

    _alembic("downgrade", "recall_reminders@-1")
    after_down = _list_tables()
    assert RECALL_REMINDERS_TABLES.isdisjoint(after_down)
    assert baseline <= after_down, (
        f"downgrade leaked beyond recall_reminders branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert before == after_up, "round-trip left schema in a different state"
