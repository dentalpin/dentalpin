"""integrations round-trip uninstall test.

Mirrors patient_relationships/recalls/schedules/whatsapp_kapso: install
-> uninstall -> reinstall must drop ONLY the integrations tables and
leave every other module untouched. The module now owns two revisions
(int_0001, int_0002 — added api_tokens), so the branch-scoped downgrade
target is ``integrations@-2`` — the same form ``_downgrade_target_for``
resolves for the real uninstall path (``_count_owned_revisions``
tracks this dynamically; this test's target is hardcoded and must be
bumped whenever a revision is added to this branch). Marked
``alembic_roundtrip`` and excluded from the default pytest run.
"""

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

INTEGRATIONS_TABLES = {"webhook_subscriptions", "webhook_deliveries", "api_tokens"}


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


def test_integrations_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert INTEGRATIONS_TABLES.issubset(before), (
        f"expected integrations tables at heads; missing: {INTEGRATIONS_TABLES - before}"
    )
    baseline_other = before - INTEGRATIONS_TABLES

    _alembic("downgrade", "integrations@-2")
    after_down = _list_tables()
    assert INTEGRATIONS_TABLES.isdisjoint(after_down), (
        f"integrations tables survived downgrade: {INTEGRATIONS_TABLES & after_down}"
    )
    assert baseline_other <= after_down, (
        f"downgrade leaked into other modules; missing: {baseline_other - after_down}"
    )

    _alembic("upgrade", "integrations@head")
    after_up = _list_tables()
    assert before <= after_up, (
        f"reinstall did not restore every table; missing: {before - after_up}"
    )
