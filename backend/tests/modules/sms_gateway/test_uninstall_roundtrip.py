"""sms_gateway round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the sms_gateway
branch's tables plus the sms template rows it seeds (smg_0002 cleans
its own rows by marker, so clinic-authored templates are untouched).
The module owns two revisions (smg_0001 tables, smg_0002 seed), so the
downgrade walks ``sms_gateway@-1`` until the settings table is gone
(inventory pattern — never ``@base``). Marked ``alembic_roundtrip``.
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

SMS_TABLES = {"sms_gateway_settings"}
SMS_HEAD = "smg_0002"
SMS_SEED_MARKER = "Seeded by sms_gateway smg_0002 (system SMS templates)"


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


async def _seed_row_count_async() -> int:
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.fetchval(
            "SELECT count(*) FROM notification_templates "
            "WHERE clinic_id IS NULL AND channel = 'sms' AND description = $1",
            SMS_SEED_MARKER,
        )
    finally:
        await conn.close()


def _seed_row_count() -> int:
    return asyncio.run(_seed_row_count_async())


def test_sms_gateway_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert SMS_TABLES.issubset(before), "sms_gateway tables missing after upgrade"
    assert _seed_row_count() == 18, "sms template seed rows missing after upgrade"

    expected_gone = SMS_TABLES | dependent_tables(SMS_HEAD)
    baseline = before - expected_gone

    after_down = before
    for _ in range(10):
        _alembic("downgrade", "sms_gateway@-1")
        after_down = _list_tables()
        if SMS_TABLES.isdisjoint(after_down):
            break
    else:
        raise AssertionError(
            f"sms_gateway tables survived full downgrade: {SMS_TABLES & _list_tables()}"
        )
    assert expected_gone.isdisjoint(after_down)
    assert _seed_row_count() == 0, "seed rows leaked past uninstall"
    assert baseline <= after_down, (
        f"downgrade leaked beyond sms_gateway branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert SMS_TABLES.issubset(after_up), "sms_gateway tables missing after re-upgrade"
    assert _seed_row_count() == 18, "seed rows missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
