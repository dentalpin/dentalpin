"""contacts round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the contacts table
plus the branches Alembic drags through ``depends_on`` edges, and
leave every other module untouched (#552). The dragged set is derived
from the live Alembic graph via the shared helper, not hardcoded, so
it stays correct as new modules declare ``depends_on`` an existing
branch (trap M6).
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

CONTACTS_TABLES = {"contacts"}
CONTACTS_HEAD = "con_0001"

# Branches Alembic drags down with ``con_0001`` through ``depends_on``
# edges (labo_0001, po_0001, rat_0001 and supp_0001 name it; sui_0001
# names supp_0001, so supplier_items follows transitively). Pinned here
# — not just derived — so a removed edge turns red instead of silently
# narrowing the drag (trap M6).
CONTACTS_DEPENDENT_TABLES = {
    "lab_orders",
    "purchase_orders",
    "purchase_order_lines",
    "purchase_receipts",
    "purchase_receipt_lines",
    "supplier_reviews",
    "suppliers",
    "supplier_items",
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


def test_contacts_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert CONTACTS_TABLES.issubset(before), "contacts tables missing after upgrade"

    expected_gone = CONTACTS_TABLES | dependent_tables(CONTACTS_HEAD)
    baseline = before - expected_gone

    _alembic("downgrade", "contacts@-1")
    after_down = _list_tables()
    assert CONTACTS_TABLES.isdisjoint(after_down), "contacts tables still present after downgrade"
    assert CONTACTS_DEPENDENT_TABLES.isdisjoint(after_down), (
        "expected M6 dependents to be dragged with contacts: "
        f"{CONTACTS_DEPENDENT_TABLES & after_down}"
    )
    assert baseline <= after_down, (
        f"downgrade leaked beyond contacts branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert CONTACTS_TABLES.issubset(after_up), "contacts tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
