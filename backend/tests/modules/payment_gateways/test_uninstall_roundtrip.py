"""payment_gateways round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the payment_gateways branch's
tables. The module owns one revision (pg_0001), so a single
``payment_gateways@-1`` step empties it (inventory pattern — never ``@base``).
Marked ``alembic_roundtrip``.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from app.config import settings
from app.modules.payment_gateways import PAYMENT_GATEWAYS_TABLES
from tests.modules._roundtrip_depends import dependent_tables

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
HEAD = "pg_0001"


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=BACKEND_ROOT,
        check=True,
    )


async def _list_tables_async() -> set[str]:
    conn = await asyncpg.connect(
        settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )
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


def test_payment_gateways_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert PAYMENT_GATEWAYS_TABLES.issubset(before), "payment_gateways tables missing after upgrade"

    expected_gone = PAYMENT_GATEWAYS_TABLES | dependent_tables(HEAD)
    baseline = before - expected_gone

    _alembic("downgrade", "payment_gateways@-1")
    after_down = _list_tables()
    assert expected_gone.isdisjoint(after_down), (
        f"payment_gateways tables survived downgrade: {expected_gone & after_down}"
    )
    assert baseline <= after_down, (
        f"downgrade leaked beyond payment_gateways branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert before == after_up, "round-trip left schema in a different state"
