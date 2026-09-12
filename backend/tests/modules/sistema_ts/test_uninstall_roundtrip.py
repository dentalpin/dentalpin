"""sistema_ts round-trip uninstall test — drops only sistema_ts_* tables."""

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
TS_TABLES = {
    "sistema_ts_settings",
    "sistema_ts_documents",
    "sistema_ts_patient_opposition",
    "sistema_ts_item_types",
}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


async def _tables_async() -> set[str]:
    conn = await asyncpg.connect(
        settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version'"
        )
        return {r["table_name"] for r in rows}
    finally:
        await conn.close()


def test_sistema_ts_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = asyncio.run(_tables_async())
    assert TS_TABLES.issubset(before)
    _alembic("downgrade", "sistema_ts@-1")
    after = asyncio.run(_tables_async())
    assert TS_TABLES.isdisjoint(after) and after == before - TS_TABLES
    _alembic("upgrade", "heads")
    assert asyncio.run(_tables_async()) == before
