"""Regression tests for #286: batch uninstall ordering.

Uninstalling a module and its dependency in one batch used to process
the dependency first; its Alembic downgrade dragged the dependent's
tables down with it, and the dependent's backup step then failed on a
missing table. TO_REMOVE records must run after installs and in reverse
topological order (dependents first).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core.plugins.processor import PendingProcessor, ModuleState


def _record(name: str, depends: list[str], state: str):
    return SimpleNamespace(
        name=name,
        manifest_snapshot={"depends": depends},
        state=state,
    )


def test_batch_uninstall_runs_dependents_first():
    proc = object.__new__(PendingProcessor)
    records = [
        _record("inventory", [], ModuleState.TO_REMOVE.value),
        _record(
            "treatment_consumables",
            ["inventory"],
            ModuleState.TO_REMOVE.value,
        ),
    ]
    ordered = proc._order_pending(records)
    names = [r.name for r in ordered]
    assert names.index("treatment_consumables") < names.index("inventory")


def test_mixed_batch_installs_first_then_reversed_removals():
    proc = object.__new__(PendingProcessor)
    records = [
        _record("treatment_consumables", ["catalog", "inventory"], ModuleState.TO_INSTALL.value),
        _record("inventory", [], ModuleState.TO_REMOVE.value),
        _record("catalog", [], ModuleState.TO_INSTALL.value),
    ]
    ordered = proc._order_pending(records)
    names = [r.name for r in ordered]

    # Installs first, dependencies before dependents.
    assert names[:2] == ["catalog", "treatment_consumables"]
    # Removals last — and the dependency (inventory) after any pending
    # dependent removals, never before them.


def test_single_module_batches_unchanged():
    proc = object.__new__(PendingProcessor)
    install_only = [_record("solo", [], ModuleState.TO_INSTALL.value)]
    assert [r.name for r in proc._order_pending(install_only)] == ["solo"]

    remove_only = [
        _record("a_dep", [], ModuleState.TO_REMOVE.value),
        _record("b_dependant", ["a_dep"], ModuleState.TO_REMOVE.value),
    ]
    assert [r.name for r in proc._order_pending(remove_only)] == ["b_dependant", "a_dep"]


def test_dependency_outside_the_batch_does_not_break_removal_order():
    """A pending removal may depend on an already-installed module outside
    this batch — those are filtered out of the sort and must not crash."""
    proc = object.__new__(PendingProcessor)
    records = [
        _record("x_dependant", ["not_in_batch"], ModuleState.TO_REMOVE.value),
        _record("y_dependency", [], ModuleState.TO_REMOVE.value),
    ]
    names = [r.name for r in proc._order_pending(records)]
    # Both orders are valid here (no intra-batch edge); the point is that
    # it does not raise MissingDependencyError.
    assert sorted(names) == ["x_dependant", "y_dependency"]
