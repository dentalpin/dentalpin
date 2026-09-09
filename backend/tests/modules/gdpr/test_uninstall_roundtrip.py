"""gdpr round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the gdpr tables and leave
every other module untouched. The module owns a single revision
(gdpr_0001), so the branch-scoped downgrade target is ``gdpr@-1``.
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

GDPR_TABLES = {
    "gdpr_requests",
    "patient_consents",
    "retention_policies",
    "gdpr_erasure_audit_logs",
    "data_breaches",
}


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


def test_gdpr_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert GDPR_TABLES.issubset(before), "gdpr tables missing after upgrade"

    _alembic("downgrade", "gdpr@-1")
    after_down = _list_tables()
    assert GDPR_TABLES.isdisjoint(after_down), "gdpr tables still present after downgrade"

    other_tables = before - GDPR_TABLES
    assert other_tables.issubset(after_down), "downgrade leaked beyond gdpr branch"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert GDPR_TABLES.issubset(after_up), "gdpr tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
