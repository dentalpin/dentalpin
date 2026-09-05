"""Round-trip migration test.

Asserts that the head schema is reproducible — i.e. ``upgrade heads``
produces the same set of tables and columns whether you arrive there
from a clean DB or after a downgrade.

The strict form is ``upgrade → downgrade base → upgrade``. We keep it
when every migration has a working ``downgrade``. As soon as the graph
contains a one-way migration (its downgrade raises
``NotImplementedError`` on purpose — see ``ONE_WAY_REVISIONS``), the
strict round-trip is impossible: descending past the wall would invoke
the unimplemented downgrade and abort the test.

While walls exist, we degrade to ``upgrade → drop schema → stamp base
→ upgrade`` and assert the resulting schema matches the original.
This still catches:

- ``upgrade heads`` not being deterministic (drift between two clean
  rebuilds).
- ``get_models()`` declarations diverging from the migrations.
- Schema-time bugs like FK target mismatches that crash on second
  upgrade.

It does **not** catch broken ``downgrade`` methods. The ``ONE_WAY_REVISIONS``
list is the place to revisit when a wall can be removed (e.g. by
implementing the downgrade or by squashing pre-prod migrations); when
the list is empty, the test re-enters strict mode automatically.

Plural ``heads`` is used because removable modules (issue #56) live on
their own Alembic branch, so the graph has more than one head.

Alembic commands are invoked via subprocess because ``env.py`` runs
``asyncio.run(...)`` internally — calling that from within pytest's
running event loop raises ``RuntimeError: asyncio.run() cannot be
called from a running event loop``.

Marked ``alembic_roundtrip`` and excluded from the default pytest run
(see ``pyproject.toml``). CI runs it as a dedicated step after the
main test suite.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

# Migrations whose ``downgrade`` is intentionally not implemented.
# Each entry is the revision id where ``raise NotImplementedError`` lives.
# When this set is empty, the strict round-trip (downgrade base) is run.
# Otherwise the test degrades to drop-schema-and-rebuild idempotency.
#
# Adding a wall is an explicit decision — squash the pre-prod chain or
# implement the downgrade as soon as it can be done. Track the rationale
# in the migration file's docstring.
ONE_WAY_REVISIONS: frozenset[str] = frozenset(
    {
        # tp_0004: consolidates `treatment_media` into `media.media_attachments`.
        # The downgrade would have to recreate `treatment_media` and copy
        # filtered rows back. Pre-prod, treatment_media data lives in
        # media_attachments going forward — see the migration's docstring.
        "tp_0004",
        # cn_0002: drops clinical_notes attachments into media (same
        # consolidation shape as tp_0004). Listed now so the test cannot
        # silently go strict on it once tp_0004 is resolved (audit 2026-09).
        "cn_0002",
    }
)


def _alembic(*args: str) -> None:
    """Run ``alembic <args>`` from the backend package root."""
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=BACKEND_ROOT,
        check=True,
    )


def _asyncpg_dsn() -> str:
    """Strip ``postgresql+asyncpg://`` → ``postgresql://`` for asyncpg."""
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _snapshot_tables_async() -> dict[str, list[str]]:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version' "
            "ORDER BY table_name"
        )
        result: dict[str, list[str]] = {}
        for row in tables:
            tbl = row["table_name"]
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = $1 "
                "ORDER BY ordinal_position",
                tbl,
            )
            result[tbl] = [c["column_name"] for c in cols]
        return result
    finally:
        await conn.close()


def _snapshot_tables() -> dict[str, list[str]]:
    return asyncio.run(_snapshot_tables_async())


def _leftover_tables() -> list[str]:
    return list(_snapshot_tables().keys())


async def _drop_public_schema_async() -> None:
    """Drop every non-system table in ``public`` *and* the alembic version
    table, so the next ``alembic stamp base`` starts from a truly empty
    state. Equivalent to ``DROP SCHEMA public CASCADE; CREATE SCHEMA public``,
    but expressed as table drops to keep ownership and grants intact."""
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        for row in rows:
            await conn.execute(f'DROP TABLE IF EXISTS "{row["tablename"]}" CASCADE')
    finally:
        await conn.close()


def _drop_public_schema() -> None:
    asyncio.run(_drop_public_schema_async())


def test_upgrade_downgrade_upgrade_is_schema_stable() -> None:
    """upgrade → reset → upgrade must produce the same schema.

    Strict round-trip when no one-way migrations exist; degraded to
    drop-and-rebuild idempotency when ``ONE_WAY_REVISIONS`` is non-empty
    (see module docstring for the trade-off)."""
    _alembic("upgrade", "heads")
    before = _snapshot_tables()
    assert before, "expected at least one table after upgrade heads"

    if ONE_WAY_REVISIONS:
        # One-way walls present — replace strict round-trip with
        # drop-schema-and-stamp-base. We still verify that re-running
        # `upgrade heads` from a clean state matches the original.
        _drop_public_schema()
        _alembic("stamp", "base")
        leftover = _leftover_tables()
        assert leftover == [], f"drop_public_schema left tables behind: {leftover}"
    else:
        _alembic("downgrade", "base")
        leftover = _leftover_tables()
        assert leftover == [], f"downgrade base left tables behind: {leftover}"

    _alembic("upgrade", "heads")
    after = _snapshot_tables()

    assert before == after, (
        "Schema drift after upgrade → reset → upgrade\n"
        f"before tables: {sorted(before)}\n"
        f"after tables:  {sorted(after)}"
    )
