"""migration_import round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the migration_import
tables and leave every other module untouched, including the media
tables its first revision ``depends_on`` (#552). The branch ships four
revisions, so the downgrade walks ``migration_import@-1`` until the
tables are gone (never ``@base``: in the merged multi-head graph it
resolves to the whole-graph base).
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

MIGRATION_IMPORT_TABLES = {
    "migration_import_jobs",
    "migration_import_entity_mappings",
    "migration_import_file_stagings",
    "migration_import_warnings",
    "migration_import_raw_entities",
    "migration_import_mapping_decisions",
}
MIGRATION_IMPORT_HEAD = "mig_0004"


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


def test_migration_import_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert MIGRATION_IMPORT_TABLES.issubset(before), "migration_import tables missing after upgrade"

    expected_gone = MIGRATION_IMPORT_TABLES | dependent_tables(MIGRATION_IMPORT_HEAD)
    baseline = before - expected_gone

    for _ in range(10):
        _alembic("downgrade", "migration_import@-1")
        after_down = _list_tables()
        if MIGRATION_IMPORT_TABLES.isdisjoint(after_down):
            break
    else:
        raise AssertionError(
            f"migration_import tables survived full downgrade: {MIGRATION_IMPORT_TABLES & _list_tables()}"
        )
    assert baseline <= after_down, (
        f"downgrade leaked beyond migration_import branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert MIGRATION_IMPORT_TABLES.issubset(after_up), (
        "migration_import tables missing after re-upgrade"
    )
    assert before == after_up, "round-trip left schema in a different state"
