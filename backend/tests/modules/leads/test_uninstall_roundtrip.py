"""leads round-trip uninstall test.

Install, uninstall, reinstall must drop ONLY this module's tables and
leave every other module untouched — including ``recalls``, which leads
declares as a dependency and must never take down with it. The
branch-scoped downgrade target is ``leads@-2`` (the branch has two revisions).
Marked ``alembic_roundtrip`` and excluded from the default run.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from app.config import settings
from app.modules.leads import LEAD_TABLES

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

# The recall branch is a declared dependency of this module: an uninstall
# that took it down would be a cross-branch leak, exactly what ADR 0002
# forbids.
DEPENDENCY_TABLES = {"recalls", "recall_contact_attempts", "recall_settings"}


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


def test_leads_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert LEAD_TABLES.issubset(before), "leads tables missing after upgrade"
    assert DEPENDENCY_TABLES.issubset(before), "recalls tables missing after upgrade"

    # Branch-scoped form (<label>@-N): plain <label>@base would downgrade
    # every branch to the shared ancestor.
    _alembic("downgrade", "leads@-2")  # the branch has two revisions now
    after_down = _list_tables()
    assert LEAD_TABLES.isdisjoint(after_down), "leads tables still present after downgrade"
    assert DEPENDENCY_TABLES.issubset(after_down), "downgrade leaked into the recalls branch"

    other_tables = before - LEAD_TABLES
    assert other_tables.issubset(after_down), "downgrade leaked beyond the leads branch"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert LEAD_TABLES.issubset(after_up), "leads tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
