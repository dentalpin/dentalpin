"""inventory_reorder round-trip uninstall test.

The module owns a single no-op revision (ir_0001) on its own
``inventory_reorder`` branch — it creates no tables. The round trip
still matters: downgrading ``inventory_reorder@-1`` (the uninstall path)
must resolve on that isolated branch and must **not** move any table —
neither drop the module's (it has none) nor leak into any other
module's schema. Marked ``alembic_roundtrip`` and excluded from the
default pytest run.
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


def test_inventory_reorder_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    baseline = _list_tables()

    # Uninstall: the no-op branch downgrades without touching a single table.
    _alembic("downgrade", "inventory_reorder@-1")
    after_down = _list_tables()
    assert baseline <= after_down, (
        f"downgrade leaked into other modules; missing: {baseline - after_down}"
    )

    # Reinstall restores the branch head (still no tables).
    _alembic("upgrade", "inventory_reorder@head")
    after_up = _list_tables()
    assert baseline <= after_up, (
        f"reinstall did not restore every table; missing: {baseline - after_up}"
    )
