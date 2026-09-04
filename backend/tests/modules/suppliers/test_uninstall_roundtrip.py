"""suppliers round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the suppliers table and
leave every other module untouched. The module owns a single revision
(supp_0001), so the branch-scoped downgrade target is ``suppliers@-1``.
Alembic ``depends_on`` dependents (e.g. a future supplier_items branch that
declares ``depends_on supp_0001``) are dragged down together and deducted
from the "must survive" set via the graph helper (trap M6).
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

SUPPLIERS_TABLES = {"suppliers"}
SUPPLIERS_HEAD = "supp_0001"


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


def test_suppliers_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert SUPPLIERS_TABLES.issubset(before), "suppliers tables missing after upgrade"

    expected_gone = SUPPLIERS_TABLES | dependent_tables(SUPPLIERS_HEAD)
    baseline = before - expected_gone

    _alembic("downgrade", "suppliers@-1")
    after_down = _list_tables()
    assert SUPPLIERS_TABLES.isdisjoint(after_down), "suppliers tables still present after downgrade"
    assert baseline <= after_down, (
        f"downgrade leaked beyond suppliers branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert SUPPLIERS_TABLES.issubset(after_up), "suppliers tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
