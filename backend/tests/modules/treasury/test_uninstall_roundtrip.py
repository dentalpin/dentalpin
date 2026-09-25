"""treasury round-trip uninstall test.

Install → uninstall → reinstall must drop ONLY the module's tables
(``treasury_accounts``, ``treasury_entries``) and leave every other
module untouched. Branch-scoped target ``treasury@-1`` — the branch is
a single revision (``tre_0001``; the former ``tre_0002``/``tre_0003``
were folded back in); the ``-N`` count
must grow with the branch. Plain ``base`` (or ``<label>@base``) would
downgrade every branch to the shared ancestor (see
_downgrade_target_for) — and a bare ``-1`` only peels the newest
revision. Marked ``alembic_roundtrip`` and excluded from the default
pytest run.
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

TRE_TABLES = {"treasury_accounts", "treasury_entries"}


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


def test_treasury_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert TRE_TABLES.issubset(before), "treasury tables missing after upgrade"

    _alembic("downgrade", "treasury@-1")
    after_down = _list_tables()
    assert TRE_TABLES.isdisjoint(after_down), "treasury tables still present after downgrade"

    other_tables = before - TRE_TABLES
    assert other_tables.issubset(after_down), "downgrade leaked beyond treasury branch"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert TRE_TABLES.issubset(after_up), "treasury tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
