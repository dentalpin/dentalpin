"""Shared Alembic-graph helper for branch-scoped uninstall round-trip tests.

Test fixtures that downgrade a single module branch must know the *correct*
set of tables that will disappear. Alembic's ``depends_on`` graph drags
dependent branches down together with their dependency (trap M6): for example
``purchase_orders`` and ``treatment_consumables`` both ``depends_on`` the
``inventory`` head, so downgrading ``inventory`` also drops their tables. This
module derives that dependent set from the actual Alembic script graph at
runtime instead of hardcoding table names, so it stays correct as new modules
declare ``depends_on`` an existing branch (inventory_reorder, supplier_ratings,
...). Model imports are limited to the dependents actually discovered.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from alembic.config import Config
from alembic.script import Script, ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


def _script_directory() -> ScriptDirectory:
    """Load the migration graph from an absolute config (cwd-independent)."""
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT))
    raw_locations = cfg.get_main_option("version_locations")
    absolute = ":".join(str((BACKEND_ROOT / part).resolve()) for part in raw_locations.split(":"))
    cfg.set_main_option("version_locations", absolute)
    return ScriptDirectory.from_config(cfg)


def _branch_revision_ids(sd: ScriptDirectory, head_revision: str) -> set[str]:
    """Revision ids making up the target branch (its head lineage)."""
    ids: set[str] = set()
    cursor = sd.get_revision(head_revision)
    while cursor is not None:
        ids.add(cursor.revision)
        cursor = sd.get_revision(cursor.down_revision) if cursor.down_revision else None
    return ids


def _resolved_ids(sd: ScriptDirectory, deps: object) -> set[str]:
    """Resolve a ``dependencies`` value to concrete revision ids."""
    if not deps:
        return set()
    tokens = deps if isinstance(deps, (list, tuple)) else (deps,)
    resolved: set[str] = set()
    for token in tokens:
        rev = sd.get_revision(token)
        if rev is not None:
            resolved.add(rev.revision)
    return resolved


def _tables_for_label(label: str) -> set[str]:
    """Table names for ``app.modules.<label>.models``."""
    module = importlib.import_module(f"app.modules.{label}.models")
    return {
        getattr(cls, "__tablename__")  # noqa: A001
        for cls in vars(module).values()
        if isinstance(cls, type) and getattr(cls, "__tablename__", None)
    }


def dependent_tables(head_revision: str) -> set[str]:
    """Tables Alembic drops *additionally* when ``head_revision``'s branch goes.

    Walks the ``depends_on`` graph: every leaf branch whose dependency closure
    reaches the target branch is dragged down on downgrade. Returns the union
    of those dependent branches' model tables (transitively).
    """
    sd = _script_directory()
    branch_ids = _branch_revision_ids(sd, head_revision)
    if not branch_ids:
        raise RuntimeError(f"unknown migration head revision: {head_revision}")

    # Build reverse map: branch_label -> scripts on that branch, plus the
    # branch each script depends on (as resolved revision ids).
    by_label: dict[str, list[Script]] = {}
    deps_by_label: dict[str, set[str]] = {}
    for script in sd.walk_revisions():
        label = next(iter(script.branch_labels)) if script.branch_labels else None
        if label:
            by_label.setdefault(label, []).append(script)
        resolved = _resolved_ids(sd, getattr(script, "dependencies", None))
        if resolved:
            deps_by_label.setdefault(label or "", set()).update(resolved)

    # All revision ids of the target branch, used to propagate the drag onward.
    dragged_ids = set(branch_ids)

    # Never report the target branch's own label (the caller owns those tables).
    target_script = sd.get_revision(head_revision)
    target_label = next(iter(target_script.branch_labels)) if target_script.branch_labels else None

    # Find labels dragged down by the target via reverse-dependency closure:
    # a label L (≠ target) is dragged if any of its dependencies is a revision
    # already being dragged; dragging L extends the dragged revision set.
    dragged: set[str] = set()
    changed = True
    while changed:
        changed = False
        for label, deps in deps_by_label.items():
            if label and label != target_label and label not in dragged and deps & dragged_ids:
                dragged.add(label)
                changed = True
                for script in by_label.get(label, ()):
                    dragged_ids.add(script.revision)

    tables: set[str] = set()
    for label in dragged:
        if label not in by_label:
            raise RuntimeError(f"dependent branch has no migrations: {label!r}")
        tables |= _tables_for_label(label)
    return tables
