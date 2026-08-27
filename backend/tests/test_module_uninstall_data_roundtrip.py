"""Backup-content integrity test for the uninstall pipeline.

Companion to ``test_uninstall_roundtrip.py`` (which verifies Alembic
branch-scoped downgrade/upgrade) and ``test_plugin_processor.py`` (pure
helpers). This test seeds a real row into a removable module's table,
runs ``PendingProcessor._dump_tables``, and asserts the produced
``.sql`` is a non-trivial pg_dump containing a recognisable INSERT for
the seeded data — so a future change that breaks the dump shape
(missing tables, empty file, wrong DSN) fails loud instead of silently
shipping corrupt backups.

Marked ``alembic_roundtrip`` because it requires a live Postgres at
``DATABASE_URL``; run with::

    pytest -m alembic_roundtrip tests/test_module_uninstall_data_roundtrip.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _seed_clinic_hours_row(clinic_id) -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        # Required parent: a clinic must exist before clinic_weekly_schedules
        # references it. Insert a minimal clinic row.
        await conn.execute(
            "INSERT INTO clinics (id, name, tax_id, settings, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4::jsonb, NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING",
            clinic_id,
            "BackupTest Clinic",
            f"BKT-{str(clinic_id)[:8]}",
            "{}",
        )
        # The actual columns of clinic_weekly_schedules are intentionally
        # narrow (id, clinic_id, is_active, timestamps) — no per-day data
        # in the parent table. Per-shift data lives elsewhere; for this
        # test we just need *one* row in the schedules-owned table so the
        # data-only pg_dump has something to emit.
        await conn.execute(
            "INSERT INTO clinic_weekly_schedules "
            "(id, clinic_id, is_active, created_at, updated_at) "
            "VALUES ($1, $2, $3, NOW(), NOW())",
            uuid4(),
            clinic_id,
            True,
        )
    finally:
        await conn.close()


async def _delete_seeded_data(clinic_id) -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("DELETE FROM clinic_weekly_schedules WHERE clinic_id = $1", clinic_id)
        await conn.execute("DELETE FROM clinics WHERE id = $1", clinic_id)
    finally:
        await conn.close()


def test_backup_contains_seeded_rows(tmp_path: Path) -> None:
    """``_dump_tables`` produces a non-empty SQL dump that includes the
    seeded clinic_weekly_schedules row — so the file an admin would use
    to restore data after an uninstall actually carries data."""
    from app.core.plugins import processor as processor_module

    clinic_id = uuid4()
    asyncio.run(_seed_clinic_hours_row(clinic_id))
    try:
        backup_root = tmp_path / "backups"
        original_root = processor_module.BACKUP_ROOT
        processor_module.BACKUP_ROOT = backup_root
        try:
            # Real session factory: _dump_tables now asks the catalog which
            # tables still exist (#298), so this test also covers that
            # lookup against a live Postgres.
            async def _dump() -> Path | None:
                from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
                from sqlalchemy.pool import NullPool

                engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
                try:
                    proc = processor_module.PendingProcessor(
                        session_factory=async_sessionmaker(engine, expire_on_commit=False)
                    )
                    return await proc._dump_tables("schedules", ["clinic_weekly_schedules"])
                finally:
                    await engine.dispose()

            backup_path = asyncio.run(_dump())
        finally:
            processor_module.BACKUP_ROOT = original_root

        assert backup_path is not None, "expected a backup file path"
        assert backup_path.exists(), "backup file was not written"
        assert backup_path.stat().st_size > 0, "backup file is empty"

        sql = backup_path.read_text(encoding="utf-8", errors="replace")
        assert "INSERT INTO" in sql or "COPY " in sql, (
            "backup contains no rows — pg_dump --data-only should emit "
            "INSERT or COPY statements for seeded data"
        )
        assert str(clinic_id) in sql, (
            "backup is missing the seeded clinic_id; pg_dump filtered "
            "the wrong table or DSN is wrong"
        )
    finally:
        asyncio.run(_delete_seeded_data(clinic_id))
