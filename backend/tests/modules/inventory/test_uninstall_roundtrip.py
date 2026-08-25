"""Branch-scoped uninstall/reinstall coverage for inventory."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip
BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
INVENTORY_TABLES = {"inventory_items", "stock_movements"}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _tables() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def test_inventory_uninstall_roundtrip_is_branch_scoped() -> None:
    """install → uninstall → reinstall drops only inventory's tables."""
    _alembic("upgrade", "heads")
    before = asyncio.run(_tables())
    assert INVENTORY_TABLES.issubset(before)
    baseline = before - INVENTORY_TABLES

    # Walk the branch down one revision at a time until the module's table
    # is gone. ``inventory@-1`` always resolves against the branch's
    # *current* head — never use ``@base`` (whole-graph base in this
    # merged multi-head graph) or a hardcoded step count.
    after_down = before
    for _ in range(10):
        _alembic("downgrade", "inventory@-1")
        after_down = asyncio.run(_tables())
        if INVENTORY_TABLES.isdisjoint(after_down):
            break
    else:
        raise AssertionError(
            f"inventory tables survived full downgrade: {INVENTORY_TABLES & asyncio.run(_tables())}"
        )
    assert baseline <= after_down

    _alembic("upgrade", "inventory@head")
    after_up = asyncio.run(_tables())
    assert before <= after_up
