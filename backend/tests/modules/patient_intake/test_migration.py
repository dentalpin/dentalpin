"""Verify the intake branch installs and rolls back independently."""

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip
BACKEND_ROOT = Path(__file__).resolve().parents[3]
INTAKE_TABLES = {
    "patient_intake_form_versions",
    "patient_intake_submissions",
    "patient_intake_consent_provenance",
}


def migrate(*args):
    subprocess.run(["alembic", *args], cwd=BACKEND_ROOT, check=True)


async def tables_and_projection():
    conn = await asyncpg.connect(settings.DATABASE_URL.replace("+asyncpg", ""))
    try:
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        has_projection = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'notification_preferences' "
            "AND column_name = 'verified_consents')"
        )
        return {row["tablename"] for row in tables}, has_projection
    finally:
        await conn.close()


def test_intake_migration_branch_round_trip():
    migrate("upgrade", "patient_intake@head")
    tables, projection = asyncio.run(tables_and_projection())
    assert INTAKE_TABLES <= tables
    assert "patient_consents" in tables
    assert projection

    migrate("upgrade", "heads")
    installed, _ = asyncio.run(tables_and_projection())
    migrate("downgrade", "patient_intake@-2")
    remaining, projection = asyncio.run(tables_and_projection())
    assert remaining == installed - INTAKE_TABLES
    assert projection

    migrate("upgrade", "patient_intake@head")
    assert asyncio.run(tables_and_projection()) == (installed, True)
