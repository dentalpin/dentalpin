"""Batch ordering and backup tolerance in the pending processor (#286).

Removing a dependency pair in one "Apply changes" batch used to process
the dependency first: its Alembic downgrade dragged the dependent's
branch down (``depends_on``), so the dependent's tables were gone by the
time its own ``pg_dump`` backup ran — exit 1, record stranded in
``to_remove``. Removals must run dependents-first; installs keep the
dependencies-first order.
"""

from __future__ import annotations

import subprocess

import pytest

from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.processor import PendingProcessor
from app.core.plugins.state import ModuleState


def _record(name: str, state: ModuleState, depends: list[str] | None = None) -> ModuleRecord:
    return ModuleRecord(
        name=name,
        version="0.1.0",
        state=state.value,
        category="official",
        removable=True,
        auto_install=False,
        manifest_snapshot={"name": name, "depends": depends or []},
    )


@pytest.fixture
def processor() -> PendingProcessor:
    # _order_pending and _dump_tables never touch the session factory.
    return PendingProcessor(session_factory=None)  # type: ignore[arg-type]


def test_removals_run_dependents_first(processor: PendingProcessor) -> None:
    """The #286 repro: inventory + treatment_consumables in one batch."""
    inventory = _record("inventory", ModuleState.TO_REMOVE)
    consumables = _record("treatment_consumables", ModuleState.TO_REMOVE, ["catalog", "inventory"])

    ordered = processor._order_pending([inventory, consumables])
    assert [r.name for r in ordered] == ["treatment_consumables", "inventory"]

    # Input order must not matter.
    ordered = processor._order_pending([consumables, inventory])
    assert [r.name for r in ordered] == ["treatment_consumables", "inventory"]


def test_installs_keep_dependencies_first_and_run_before_removals(
    processor: PendingProcessor,
) -> None:
    foo = _record("foo", ModuleState.TO_INSTALL)
    bar = _record("bar", ModuleState.TO_INSTALL, ["foo"])
    inventory = _record("inventory", ModuleState.TO_REMOVE)
    consumables = _record("treatment_consumables", ModuleState.TO_REMOVE, ["inventory"])

    ordered = processor._order_pending([consumables, bar, inventory, foo])
    assert [r.name for r in ordered] == [
        "foo",
        "bar",
        "treatment_consumables",
        "inventory",
    ]


def test_removal_chain_of_three_reverses_fully(processor: PendingProcessor) -> None:
    a = _record("a", ModuleState.TO_REMOVE)
    b = _record("b", ModuleState.TO_REMOVE, ["a"])
    c = _record("c", ModuleState.TO_REMOVE, ["b"])

    ordered = processor._order_pending([a, c, b])
    assert [r.name for r in ordered] == ["c", "b", "a"]


@pytest.mark.asyncio
async def test_dump_tables_skips_when_tables_are_gone(
    processor: PendingProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """pg_dump's 'no matching tables' is a skipped backup, not a failure."""
    from app.core.plugins import processor as processor_module

    monkeypatch.setattr(processor_module, "BACKUP_ROOT", tmp_path)

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN003
        raise subprocess.CalledProcessError(
            1, args, stderr=b"pg_dump: error: no matching tables were found\n"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = await processor._dump_tables("ghost", ["ghost_table"])
    assert result is None
    assert list(tmp_path.iterdir()) == []  # no empty backup file left behind


@pytest.mark.asyncio
async def test_dump_tables_still_raises_on_other_pg_dump_errors(
    processor: PendingProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from app.core.plugins import processor as processor_module

    monkeypatch.setattr(processor_module, "BACKUP_ROOT", tmp_path)

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN003
        raise subprocess.CalledProcessError(
            1, args, stderr=b"pg_dump: error: connection to server failed\n"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="connection to server failed"):
        await processor._dump_tables("mod", ["mod_table"])
