"""imaging_ai round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the imaging_ai_jobs table
and leave every other module untouched. The module owns a single revision
(aij_0001), so the branch-scoped downgrade target is ``imaging_ai@-1``.
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

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

IMAGING_AI_TABLES = {"imaging_ai_jobs"}


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


def test_imaging_ai_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert IMAGING_AI_TABLES.issubset(before), "imaging_ai tables missing after upgrade"

    _alembic("downgrade", "imaging_ai@-1")
    after_down = _list_tables()
    assert IMAGING_AI_TABLES.isdisjoint(after_down), (
        "imaging_ai tables still present after downgrade"
    )

    other_tables = before - IMAGING_AI_TABLES
    assert other_tables.issubset(after_down), "downgrade leaked beyond imaging_ai branch"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert IMAGING_AI_TABLES.issubset(after_up), "imaging_ai tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
