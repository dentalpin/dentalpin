"""Branch-scoped uninstall/reinstall coverage for documents."""

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
DOCUMENTS_TABLES = {"generated_documents"}
# No other module depends on the ``documents`` branch, so a downgrade
# tears down only this branch's tables.
DEPENDENT_TABLES: set[str] = set()


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _tables() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def test_documents_uninstall_roundtrip_is_branch_scoped() -> None:
    """install → uninstall → reinstall drops only documents' tables.

    ``documents`` is a leaf branch chained off the core ``0001`` anchor
    with ``depends_on = ("pat_0003",)`` (ordering only — downgrading
    this branch never drags the patients chain down), so the teardown
    set is exactly the module's own table(s).
    """
    _alembic("upgrade", "heads")
    before = asyncio.run(_tables())
    assert DOCUMENTS_TABLES.isdisjoint(DEPENDENT_TABLES), (
        "dependent tables overlap documents tables"
    )
    expected_gone = DOCUMENTS_TABLES | DEPENDENT_TABLES
    baseline = before - expected_gone

    # Walk the branch down one revision at a time until the module's
    # table is gone. ``documents@-1`` always resolves against the
    # branch's *current* head — never ``@base`` or a hardcoded step.
    after_down = before
    for _ in range(10):
        _alembic("downgrade", "documents@-1")
        after_down = asyncio.run(_tables())
        if DOCUMENTS_TABLES.isdisjoint(after_down):
            break
    else:
        raise AssertionError(
            f"documents tables survived full downgrade: {DOCUMENTS_TABLES & asyncio.run(_tables())}"
        )
    assert expected_gone.isdisjoint(after_down)
    assert baseline <= after_down

    # Bring everything back.
    _alembic("upgrade", "heads")
    after_up = asyncio.run(_tables())
    assert before <= after_up
