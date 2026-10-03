"""Tests for Alembic's dynamic version_locations.

Covers ``app.core.plugins.alembic_paths.discover_version_locations`` as
a pure function plus a full round-trip through ``ScriptDirectory`` to
confirm that Alembic picks up a per-module branch when the directory
exists — without needing a live database connection.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.plugins.alembic_paths import discover_version_locations


def test_discovery_empty_modules_root(tmp_path: Path) -> None:
    main_linear = tmp_path / "alembic" / "versions"
    main_linear.mkdir(parents=True)
    modules_root = tmp_path / "modules"
    modules_root.mkdir()

    locs = discover_version_locations(main_linear, modules_root)
    assert locs == [str(main_linear)]


def test_discovery_ignores_missing_modules_root(tmp_path: Path) -> None:
    main_linear = tmp_path / "alembic" / "versions"
    main_linear.mkdir(parents=True)
    modules_root = tmp_path / "does-not-exist"

    locs = discover_version_locations(main_linear, modules_root)
    assert locs == [str(main_linear)]


def test_discovery_includes_branch_directories(tmp_path: Path) -> None:
    main_linear = tmp_path / "alembic" / "versions"
    main_linear.mkdir(parents=True)
    modules_root = tmp_path / "modules"

    # Two modules with branches, one without, one with ``_`` prefix.
    for name in ("alpha", "beta"):
        (modules_root / name / "migrations" / "versions").mkdir(parents=True)
    (modules_root / "gamma").mkdir(parents=True)
    (modules_root / "_scratch").mkdir(parents=True)
    (modules_root / "_scratch" / "migrations" / "versions").mkdir(parents=True)

    locs = discover_version_locations(main_linear, modules_root)

    assert str(main_linear) in locs
    assert str(modules_root / "alpha" / "migrations" / "versions") in locs
    assert str(modules_root / "beta" / "migrations" / "versions") in locs
    # Modules without migrations/ are skipped.
    assert not any("gamma" in loc for loc in locs)
    # Underscore-prefixed modules are skipped.
    assert not any("_scratch" in loc for loc in locs)


def test_discovery_ignores_files_at_modules_root(tmp_path: Path) -> None:
    main_linear = tmp_path / "alembic" / "versions"
    main_linear.mkdir(parents=True)
    modules_root = tmp_path / "modules"
    modules_root.mkdir()
    (modules_root / "stray.txt").write_text("not a module")

    locs = discover_version_locations(main_linear, modules_root)
    assert locs == [str(main_linear)]


def test_alembic_scripts_see_branch_heads(tmp_path: Path) -> None:
    """Full chain: Alembic ScriptDirectory with two heads — main + branch."""
    # Scratch alembic dir with a main-linear single revision.
    alembic_dir = tmp_path / "alembic"
    main_linear = alembic_dir / "versions"
    main_linear.mkdir(parents=True)

    _write_revision(
        main_linear,
        rev_id="main0001",
        down_revision=None,
        branch_labels=None,
        name="initial_main",
    )

    # Brand-new module with its own branch.
    modules_root = tmp_path / "modules"
    branch_dir = modules_root / "sample" / "migrations" / "versions"
    branch_dir.mkdir(parents=True)

    _write_revision(
        branch_dir,
        rev_id="smpl0001",
        down_revision=None,
        branch_labels="'sample',",
        name="initial_sample",
    )

    # Minimal env.py stub — not executed here, ScriptDirectory only reads
    # .py files in version_locations. A placeholder suffices.
    (alembic_dir / "env.py").write_text("")
    (alembic_dir / "script.py.mako").write_text(_SCRIPT_TEMPLATE)

    # Compose an Alembic Config mirroring production wiring.
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("version_path_separator", "os")
    cfg.set_main_option(
        "version_locations",
        os.pathsep.join(discover_version_locations(main_linear, modules_root)),
    )

    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    assert heads == {"main0001", "smpl0001"}

    # Branch label lookup works.
    branch_head = script.get_revision("sample@head")
    assert branch_head is not None
    assert branch_head.revision == "smpl0001"


def test_core_spine_modules_are_not_removable() -> None:
    """#533: core 0002..0008 descend from a module revision, so every
    module on that spine must be removable=False — otherwise
    uninstalling it would drag the core chain down with it."""
    from app.core.plugins.alembic_paths import _load_script_directory
    from app.core.plugins.loader import discover_modules

    backend_root = Path(__file__).resolve().parents[1]
    core_dir = (backend_root / "alembic" / "versions").resolve()
    modules_root = (backend_root / "app" / "modules").resolve()

    script = _load_script_directory()
    by_rev = {rev.revision: rev for rev in script.walk_revisions()}

    def _module_of(rev) -> str | None:
        path = getattr(rev, "path", None)
        if not path:
            return None
        try:
            rel = Path(path).resolve().relative_to(modules_root)
        except ValueError:
            return None
        return rel.parts[0]

    def _is_core(rev) -> bool:
        path = getattr(rev, "path", None)
        if not path:
            return False
        try:
            Path(path).resolve().relative_to(core_dir)
        except ValueError:
            return False
        return True

    spine_modules: set[str] = set()
    for rev in by_rev.values():
        if not _is_core(rev):
            continue
        seen: set[str] = set()
        stack = [rev.revision]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            node = by_rev.get(current)
            if node is None:
                continue
            module = _module_of(node)
            if module is not None:
                spine_modules.add(module)
            down = node.down_revision
            if isinstance(down, str):
                stack.append(down)
            elif down:
                stack.extend(down)

    assert spine_modules, "expected at least one module on the core spine"
    manifests = {m.manifest["name"]: m.manifest for m in discover_modules()}
    for name in sorted(spine_modules):
        assert manifests[name].get("removable") is False, name


# --- Helpers --------------------------------------------------------------


_SCRIPT_TEMPLATE = """\
\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"


revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
"""


def _write_revision(
    target: Path,
    *,
    rev_id: str,
    down_revision: str | None,
    branch_labels: str | None,
    name: str,
) -> None:
    down_expr = repr(down_revision)
    branch_expr = f"({branch_labels})" if branch_labels is not None else "None"

    body = f'''"""{name}

Revision ID: {rev_id}
Revises: {down_revision or ""}

"""

revision = "{rev_id}"
down_revision = {down_expr}
branch_labels = {branch_expr}
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''
    (target / f"{rev_id}_{name}.py").write_text(body)
