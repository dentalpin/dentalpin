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


async def schema_state():
    conn = await asyncpg.connect(settings.DATABASE_URL.replace("+asyncpg", ""))
    try:
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        has_projection = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'notification_preferences' "
            "AND column_name = 'verified_consents')"
        )
        heads = await conn.fetch("SELECT version_num FROM alembic_version")
        return (
            {row["tablename"] for row in tables},
            has_projection,
            {row["version_num"] for row in heads},
        )
    finally:
        await conn.close()


def test_intake_migration_branch_round_trip():
    migrate("upgrade", "patient_intake@head")
    tables, _, _ = asyncio.run(schema_state())
    assert {*INTAKE_TABLES, "patients"} <= tables

    migrate("upgrade", "heads")
    installed, projection, heads = asyncio.run(schema_state())
    assert "patient_consents" in installed
    assert projection
    migrate("downgrade", "patient_intake@-2")
    remaining, projection, _ = asyncio.run(schema_state())
    assert remaining == installed - INTAKE_TABLES
    assert projection

    migrate("upgrade", "patient_intake@head")
    assert asyncio.run(schema_state()) == (installed, True, heads)


def test_notifications_verified_consent_revision_round_trips_independently():
    migrate("upgrade", "heads")
    tables, projection, heads = asyncio.run(schema_state())
    assert projection
    assert INTAKE_TABLES <= tables
    assert "notif_0009" in heads

    migrate("downgrade", "notif_0009@-1")
    assert asyncio.run(schema_state()) == (tables, False, (heads - {"notif_0009"}) | {"notif_0008"})

    migrate("upgrade", "notif_0009")
    assert asyncio.run(schema_state()) == (tables, True, heads)
