"""``dentalpin db ...`` subcommands.

``db upgrade`` is what the container entrypoint runs before uvicorn
instead of ``alembic upgrade heads`` (ADR 0020): it applies the core
heads plus the branch head of every module that is ``installed`` — or,
when ``core_module`` has no row for it yet, whose manifest says
``auto_install``. A branch nobody installed is never applied, so an
uninstalled module's tables do not come back on the next restart
(issue #91). Installing a module applies its branch through the pending
processor, as before.

Runs Alembic in-process: there is no event loop in the CLI, so
``env.py``'s ``asyncio.run`` is fine here (the lifespan can't do that,
hence the processor's subprocess).
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.core.plugins.alembic_paths import alembic_cfg_path, boot_upgrade_targets
from app.core.plugins.loader import register_discovered
from app.core.plugins.state import ModuleState
from app.database import async_session_maker


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("db", help="Database schema operations")
    db_sub = parser.add_subparsers(dest="db_command", required=True)

    p_upgrade = db_sub.add_parser(
        "upgrade",
        help="Apply core migrations plus the branches of installed modules (boot step)",
    )
    p_upgrade.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Alembic targets without applying them",
    )
    p_upgrade.set_defaults(func=_cmd_upgrade)

    p_backup = db_sub.add_parser(
        "backup",
        help="Full-database pg_dump plus storage snapshot for disaster recovery",
    )
    p_backup.add_argument(
        "--out-dir",
        default=None,
        help="Backup directory (default: <storage>/backups)",
    )
    p_backup.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Retain the newest N backups per kind (default: 7)",
    )
    p_backup.add_argument(
        "--skip-storage",
        action="store_true",
        help="Skip the storage tarball (database dump only)",
    )
    p_backup.set_defaults(func=_cmd_backup)


def _cmd_upgrade(args: argparse.Namespace) -> int:
    modules = register_discovered()
    states = asyncio.run(_load_states())

    def wanted(module) -> bool:
        state = states.get(module.name)
        if state is None:
            return module.get_manifest().auto_install
        return state == ModuleState.INSTALLED.value

    targets = boot_upgrade_targets(modules, wanted)
    if not targets:
        print("db upgrade: no Alembic targets (no script directory?)")
        return 1

    print(f"db upgrade: targets = {targets}")
    if args.dry_run:
        return 0

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(alembic_cfg_path()))
    for target in targets:
        command.upgrade(cfg, target)
    print(f"db upgrade: applied {len(targets)} target(s)")
    return 0


async def _load_states() -> dict[str, str]:
    """``name -> state`` from ``core_module``, or ``{}`` before the table exists."""
    async with async_session_maker() as session:
        exists = await session.scalar(text("SELECT to_regclass('core_module')"))
        if exists is None:
            return {}
        rows = await session.execute(text("SELECT name, state FROM core_module"))
        return {name: state for name, state in rows.all()}


def backup_out_dir(out_dir: str | None) -> Path:
    """Resolve the backup directory (explicit arg wins, else the storage volume)."""
    return Path(out_dir) if out_dir else Path(settings.STORAGE_LOCAL_PATH) / "backups"


def prune_backups(
    out_dir: Path, prefix: str, keep: int, protect: set[Path] = frozenset()
) -> list[Path]:
    """Delete all but the newest ``keep`` files starting with ``prefix``.

    ``keep`` is floored at 1 and files in ``protect`` (just written by
    this run) are never pruned. Returns the pruned paths.
    Lexicographic order == chronological order because every backup
    filename embeds a ``%Y%m%dT%H%M%SZ`` timestamp.
    """
    keep = max(keep, 1)
    candidates = sorted(out_dir.glob(f"{prefix}*"))
    pruned = [p for p in candidates[: max(0, len(candidates) - keep)] if p not in protect]
    for path in pruned:
        path.unlink()
    return pruned


def _dsn_and_env(dsn: str) -> tuple[str, dict]:
    """Split the password out of the DSN into ``PGPASSWORD`` so the
    secret never appears in the process list (``ps``)."""
    import os
    from urllib.parse import urlparse, urlunparse

    parts = urlparse(dsn)
    env = dict(os.environ)
    password = parts.password or ""
    if password:
        env["PGPASSWORD"] = password
        netloc = parts.hostname or ""
        if parts.port:
            netloc += f":{parts.port}"
        if parts.username:
            netloc = f"{parts.username}@{netloc}"
        dsn = urlunparse(parts._replace(netloc=netloc))
    return dsn, env


def dump_database(dsn: str, target: Path) -> str | None:
    """Stream ``pg_dump --format=custom`` into ``target``. None on success,
    else a human-readable error (missing binary, failure, empty output).

    Streams to disk (never buffers the dump in memory) and passes the
    password via ``PGPASSWORD``, never the command line.
    """
    if shutil.which("pg_dump") is None:
        return "pg_dump not found on PATH; cannot back up the database"
    clean_dsn, env = _dsn_and_env(dsn)
    try:
        with target.open("wb") as handle:
            proc = subprocess.run(
                ["pg_dump", "--format=custom", "--no-owner", clean_dsn],
                stdout=handle,
                stderr=subprocess.PIPE,
                timeout=3600,
                env=env,
            )
    except subprocess.TimeoutExpired:
        return "pg_dump timed out after 3600 seconds"
    if proc.returncode != 0:
        return f"pg_dump failed: {proc.stderr.decode(errors='replace').strip()}"
    if target.stat().st_size == 0:
        return "pg_dump produced an empty backup"
    return None


def snapshot_storage(storage_root: Path, target: Path, out_dir: Path) -> None:
    """Tarball the storage volume, excluding the backup destination
    itself (it may live inside the volume — archiving it would recurse)."""
    with tarfile.open(target, "w:gz") as tar:
        for child in sorted(storage_root.iterdir()):
            if child == out_dir or child.name == "backups":
                continue
            tar.add(child, arcname=child.name)


def _cmd_backup(args: argparse.Namespace) -> int:
    from app.core.plugins.processor import _pg_dump_dsn

    if args.keep < 1:
        print("db backup: --keep must be >= 1", flush=True)
        return 2
    out_dir = backup_out_dir(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    db_target = out_dir / f"full_{timestamp}.dump"
    error = dump_database(_pg_dump_dsn(settings.DATABASE_URL), db_target)
    if error is not None:
        print(f"db backup: {error}", flush=True)
        return 3
    print(f"db backup: database -> {db_target}")
    written = {db_target}

    if not args.skip_storage:
        storage_target = out_dir / f"storage_{timestamp}.tar.gz"
        snapshot_storage(Path(settings.STORAGE_LOCAL_PATH), storage_target, out_dir)
        print(f"db backup: storage -> {storage_target}")
        written.add(storage_target)
        pruned = prune_backups(out_dir, "storage_", args.keep, protect=written)
    else:
        pruned = []
    pruned += prune_backups(out_dir, "full_", args.keep, protect=written)
    for path in pruned:
        print(f"db backup: pruned {path.name}")
    return 0
