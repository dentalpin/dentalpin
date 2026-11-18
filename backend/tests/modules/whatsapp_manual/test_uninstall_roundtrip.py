"""Test that removing the manual adapter rolls back only its Alembic branch."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

MANUAL_TABLES = {"whatsapp_manual_delivery_declarations"}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


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


def _check_declaration_clinic_schema(connection: Connection) -> None:
    schema = inspect(connection)
    table = "whatsapp_manual_delivery_declarations"
    columns = {column["name"]: column for column in schema.get_columns(table)}
    assert columns["clinic_id"]["nullable"] is False
    assert any(
        fk["constrained_columns"] == ["clinic_id"]
        and fk["referred_table"] == "clinics"
        and fk["referred_columns"] == ["id"]
        for fk in schema.get_foreign_keys(table)
    )
    assert any(index["column_names"] == ["clinic_id"] for index in schema.get_indexes(table))


async def _check_declaration_clinic_schema_async() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_check_declaration_clinic_schema)
    finally:
        await engine.dispose()


def test_whatsapp_manual_uninstall_roundtrip_is_branch_scoped() -> None:
    # Install on an empty schema to verify that Alembic applies the
    # notifications dependency before creating the foreign key.
    _alembic("upgrade", "whatsapp_manual@head")
    assert {"communication_messages", *MANUAL_TABLES}.issubset(_list_tables())
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert MANUAL_TABLES.issubset(before), (
        f"expected whatsapp_manual tables at heads; missing: {MANUAL_TABLES - before}"
    )
    baseline_other = before - MANUAL_TABLES

    _alembic("downgrade", "whatsapp_manual@-2")
    after_down = _list_tables()
    assert MANUAL_TABLES.isdisjoint(after_down), "uninstall left whatsapp_manual tables behind"
    assert after_down == baseline_other, "uninstall touched other modules' tables"

    _alembic("upgrade", "whatsapp_manual@head")
    after_up = _list_tables()
    assert after_up == before, "reinstall did not restore the schema"
    asyncio.run(_check_declaration_clinic_schema_async())
