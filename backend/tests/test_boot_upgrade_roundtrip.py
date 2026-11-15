"""``dentalpin db upgrade`` respects install state across restarts (ADR 0020).

The bug from issue #91: uninstall downgraded a module's branch, and the
next boot's ``alembic upgrade heads`` recreated its tables with the row
still ``uninstalled``. Drives the real CLI + Alembic via subprocess against
the test DB, like ``test_uninstall_roundtrip``.

Marked ``alembic_roundtrip`` — excluded from the default run.
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

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

PERIO_TABLES = {"periodontogram_snapshots", "periodontogram_teeth", "periodontogram_sites"}


def _run(*args: str) -> None:
    command = [sys.executable, *args[1:]] if args[0] == "python" else list(args)
    subprocess.run(command, cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _sql(query: str, *params) -> list:
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.fetch(query, *params)
    finally:
        await conn.close()


def _tables() -> set[str]:
    rows = asyncio.run(
        _sql(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
    )
    return {r["table_name"] for r in rows}


def _drop_everything() -> None:
    """Empty ``public`` (tables + alembic_version) — ``downgrade base`` is not
    an option while the graph has a one-way migration (see
    ``test_alembic_roundtrip.ONE_WAY_REVISIONS``)."""
    rows = asyncio.run(_sql("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    for row in rows:
        asyncio.run(_sql(f'DROP TABLE IF EXISTS "{row["tablename"]}" CASCADE'))


def _set_state(name: str, state: str) -> None:
    asyncio.run(
        _sql(
            """
            INSERT INTO core_module (name, version, state, category, removable, auto_install,
                                     last_state_change, manifest_snapshot)
            VALUES ($1, '0.0.0', $2, 'official', true, false, now(), '{}'::jsonb)
            ON CONFLICT (name) DO UPDATE SET state = EXCLUDED.state
            """,
            name,
            state,
        )
    )


def test_db_upgrade_applies_only_core_and_installed_branches() -> None:
    _drop_everything()

    # Fresh DB, no core_module rows: core + auto_install modules only.
    _run("python", "-m", "app.cli", "db", "upgrade")
    tables = _tables()
    assert "users" in tables and "core_module" in tables
    assert PERIO_TABLES.isdisjoint(tables), (
        f"opt-in branch applied on fresh boot: {PERIO_TABLES & tables}"
    )

    # Admin installs periodontogram: its branch is applied on the next boot.
    _set_state("periodontogram", "installed")
    _run("python", "-m", "app.cli", "db", "upgrade")
    assert PERIO_TABLES.issubset(_tables())

    # Uninstall (the processor downgrades ``<label>@-<owned revisions>`` —
    # one file for periodontogram — and writes uninstalled), then
    # restart: the tables must NOT come back — the #91 bug.
    _run("alembic", "-c", str(ALEMBIC_INI), "downgrade", "periodontogram@-1")
    _set_state("periodontogram", "uninstalled")
    assert PERIO_TABLES.isdisjoint(_tables())
    _run("python", "-m", "app.cli", "db", "upgrade")
    assert PERIO_TABLES.isdisjoint(_tables()), "uninstalled module's tables resurrected on restart"

    # Leave the DB at heads for whatever runs next in this job.
    _run("alembic", "-c", str(ALEMBIC_INI), "upgrade", "heads")
