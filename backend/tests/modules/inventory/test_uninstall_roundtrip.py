"""Inventory round-trip uninstall test (issue #220).

Mirrors the recalls uninstall pattern: install → uninstall → reinstall
must drop only the inventory tables and leave every other module untouched.

Marked ``alembic_roundtrip`` and excluded from the default pytest run.
"""

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

INVENTORY_TABLES = {
    "inventory_categories",
    "inventory_items",
}


def _alembic(*args: str) -> None:
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), *args],
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


def test_inventory_uninstall_roundtrip_is_branch_scoped() -> None:
    """install → uninstall → reinstall drops only inventory tables."""
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert INVENTORY_TABLES.issubset(before), (
        f"expected inventory tables at heads; missing: {INVENTORY_TABLES - before}"
    )
    baseline_other = before - INVENTORY_TABLES

    _alembic("downgrade", "inventory@-1")

    after_down = _list_tables()
    assert INVENTORY_TABLES.isdisjoint(after_down), (
        f"inventory tables survived downgrade: {INVENTORY_TABLES & after_down}"
    )
    assert baseline_other <= after_down, (
        f"downgrade leaked into other modules; missing: {baseline_other - after_down}"
    )

    _alembic("upgrade", "inventory@head")
    after_up = _list_tables()
    assert before <= after_up, (
        f"reinstall did not restore every table; missing: {before - after_up}"
    )
