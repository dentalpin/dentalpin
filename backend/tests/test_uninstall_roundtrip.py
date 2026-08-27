"""Integration test for the hardened module uninstall pipeline (issue #56).

Two scenarios:

* **Schedules roundtrip** — drives Alembic via subprocess to prove that
  ``alembic downgrade schedules@base`` drops only schedules tables and
  leaves every other module's schema untouched, and that
  ``alembic upgrade schedules@head`` restores them. This exercises the
  combined Bug #1 (right downgrade target) + Bug #2 (branch isolation)
  fix.
* **pg_dump hard-fail** — monkeypatches ``pg_dump`` out of ``PATH`` and
  asserts that ``PendingProcessor._dump_tables`` raises ``RuntimeError``
  instead of returning ``None`` silently.

Marked ``alembic_roundtrip`` and excluded from the default pytest run
(same policy as ``test_alembic_roundtrip``).
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

SCHEDULES_TABLES = {
    "clinic_weekly_schedules",
    "clinic_overrides",
    "professional_weekly_schedules",
    "professional_overrides",
    "schedule_shifts",
}

PERIODONTOGRAM_TABLES = {
    "periodontogram_snapshots",
    "periodontogram_teeth",
    "periodontogram_sites",
}


def _alembic(*args: str) -> None:
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), *args],
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


def test_schedules_uninstall_roundtrip_is_branch_scoped() -> None:
    """install → uninstall → reinstall drops only schedules' tables."""
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert SCHEDULES_TABLES.issubset(before), (
        f"expected schedules tables at heads; missing: {SCHEDULES_TABLES - before}"
    )
    baseline_non_schedules = before - SCHEDULES_TABLES

    # Branch-scoped downgrade — the uninstall path the processor now uses.
    # ``<label>@-N`` walks N steps back on the labelled branch; schedules
    # ships one revision so N=1.
    _alembic("downgrade", "schedules@-1")

    after_down = _list_tables()
    assert SCHEDULES_TABLES.isdisjoint(after_down), (
        f"schedules tables survived downgrade: {SCHEDULES_TABLES & after_down}"
    )
    assert baseline_non_schedules <= after_down, (
        "downgrade leaked into other modules; missing tables: "
        f"{baseline_non_schedules - after_down}"
    )

    # Reinstall via the same branch head the processor uses for install.
    _alembic("upgrade", "schedules@head")
    after_up = _list_tables()
    assert before <= after_up, (
        f"reinstall did not restore every table; missing: {before - after_up}"
    )


def test_periodontogram_uninstall_roundtrip_is_branch_scoped() -> None:
    """install → uninstall → reinstall drops only periodontogram's tables.

    Mirrors the schedules round-trip: the partial unique index protecting
    the single-draft invariant must also be re-created cleanly. The module
    ships one revision so ``periodontogram@-1`` is equivalent to ``base``.
    """
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert PERIODONTOGRAM_TABLES.issubset(before), (
        f"expected periodontogram tables at heads; missing: {PERIODONTOGRAM_TABLES - before}"
    )
    baseline_non_periodontogram = before - PERIODONTOGRAM_TABLES

    _alembic("downgrade", "periodontogram@-1")

    after_down = _list_tables()
    assert PERIODONTOGRAM_TABLES.isdisjoint(after_down), (
        f"periodontogram tables survived downgrade: {PERIODONTOGRAM_TABLES & after_down}"
    )
    assert baseline_non_periodontogram <= after_down, (
        "downgrade leaked into other modules; missing tables: "
        f"{baseline_non_periodontogram - after_down}"
    )

    _alembic("upgrade", "periodontogram@head")
    after_up = _list_tables()
    assert before <= after_up, (
        f"reinstall did not restore every table; missing: {before - after_up}"
    )


MEDICAL_REFERENCE_TABLES = {
    "medical_reference_allergy",
    "medical_reference_medication",
    "medical_reference_disease",
    "medical_reference_surgery",
    "medical_reference_interaction",
    "medical_reference_contraindication",
}


def test_medical_reference_uninstall_roundtrip_is_branch_scoped() -> None:
    """install → uninstall → reinstall drops only medical_reference's tables.

    The module is ``removable=True`` with its own Alembic branch rooted on
    core ``"0001"``, so uninstalling must drop exactly its six tables and
    leave every other module — including patients_clinical's four history
    tables that hold the loose (FK-less) ``reference_id`` link — intact.
    """
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert MEDICAL_REFERENCE_TABLES.issubset(before), (
        f"expected medical_reference tables at heads; missing: {MEDICAL_REFERENCE_TABLES - before}"
    )
    baseline_non_medical_reference = before - MEDICAL_REFERENCE_TABLES

    # Walk the branch down one revision at a time until every module table
    # is gone. ``medical_reference@-1`` always resolves against the
    # branch's *current* head, so this uninstalls the module completely
    # regardless of how many ``mr_*`` revisions ship later.
    # (Do NOT use ``medical_reference@base`` here: in this repo's merged
    # multi-head graph it resolves to the whole-graph base and tears down
    # unrelated chains — tp_0004 even refuses to downgrade.)
    for _ in range(10):
        _alembic("downgrade", "medical_reference@-1")
        after_down = _list_tables()
        if MEDICAL_REFERENCE_TABLES.isdisjoint(after_down):
            break
    else:
        raise AssertionError(
            f"medical_reference tables survived full downgrade: {MEDICAL_REFERENCE_TABLES & _list_tables()}"
        )
    assert baseline_non_medical_reference <= after_down, (
        "downgrade leaked into other modules; missing tables: "
        f"{baseline_non_medical_reference - after_down}"
    )

    _alembic("upgrade", "medical_reference@head")
    after_up = _list_tables()
    assert before <= after_up, (
        f"reinstall did not restore every table; missing: {before - after_up}"
    )


async def _all_tables_exist(tables: list[str]) -> set[str]:
    """Fake the #298 catalog lookup: every requested table exists."""
    return set(tables)


def test_dump_tables_hard_fails_when_pg_dump_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without pg_dump on PATH the backup must raise, not silently skip."""
    from app.core.plugins import processor as processor_module

    monkeypatch.setattr(processor_module, "BACKUP_ROOT", tmp_path / "backups")

    def _raise_not_found(*_args, **_kwargs):
        raise FileNotFoundError("pg_dump")

    monkeypatch.setattr(processor_module.subprocess, "run", _raise_not_found)

    # Build a processor with a dummy session factory and fake the catalog
    # lookup (#298) — the failure under test is pg_dump's, not the DB's.
    proc = processor_module.PendingProcessor(session_factory=lambda: None)  # type: ignore[arg-type]
    monkeypatch.setattr(proc, "_existing_tables", _all_tables_exist)

    with pytest.raises(RuntimeError, match="pg_dump not available"):
        asyncio.run(proc._dump_tables("schedules", ["clinic_weekly_schedules"]))


def test_dump_tables_hard_fails_on_empty_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A zero-byte dump counts as a silent corruption and must raise."""
    from app.core.plugins import processor as processor_module

    monkeypatch.setattr(processor_module, "BACKUP_ROOT", tmp_path / "backups")

    def _fake_run(args, *, stdout, check, timeout=None, stderr=None):  # noqa: ARG001
        # stdout is the open file handle; write nothing → zero bytes.
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(processor_module.subprocess, "run", _fake_run)

    proc = processor_module.PendingProcessor(session_factory=lambda: None)  # type: ignore[arg-type]
    monkeypatch.setattr(proc, "_existing_tables", _all_tables_exist)

    with pytest.raises(RuntimeError, match="empty backup"):
        asyncio.run(proc._dump_tables("schedules", ["clinic_weekly_schedules"]))
