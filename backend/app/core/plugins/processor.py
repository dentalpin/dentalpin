"""Lifespan processor for pending module operations.

Runs once at FastAPI startup, after the registry has been populated
and reconciled. Walks every module in ``to_install`` / ``to_upgrade``
/ ``to_remove`` (topological order) and executes the corresponding
step sequence, writing each step to :class:`OperationLog`.

Execution is intentionally best-effort-per-module: a failure on one
module is recorded in ``core_module.error_message`` and does not stop
the rest from being processed. The admin resolves failures via CLI
(retry install, force uninstall, etc.).
"""

from __future__ import annotations

import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings

from .alembic_paths import alembic_cfg_path
from .context import ModuleContext
from .db_models import ModuleRecord
from .external_id import ExternalIdHelper
from .operation_log import OperationLog
from .registry import module_registry
from .service import ModuleService
from .state import ModuleState
from .topology import topological_sort
from .yaml_loader import load_module_data_files

if TYPE_CHECKING:
    from .base import BaseModule

logger = logging.getLogger(__name__)


BACKUP_ROOT = Path(settings.STORAGE_LOCAL_PATH) / "backups"


class PendingProcessor:
    """Resolve pending state transitions at boot."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._op_log = OperationLog(session_factory)

    async def run(self) -> list[str]:
        """Process every pending module. Returns the processed names."""
        processed: list[str] = []

        pending = await self._load_pending()
        if pending:
            ordered = self._order_pending(pending)
            logger.info(
                "Processing pending modules: %s",
                [(r.name, r.state) for r in ordered],
            )

            for record in ordered:
                try:
                    await self._process_one(record)
                    processed.append(record.name)
                except Exception as exc:
                    logger.exception(
                        "Pending operation for %s (%s) failed",
                        record.name,
                        record.state,
                    )
                    await self._mark_error(record.name, str(exc))

        # Regenerate frontend modules.json so the Nuxt host picks up any
        # newly installed/uninstalled community layers on next build.
        # Runs every boot (even when no pending operations) so manual
        # edits and drift also self-heal.
        try:
            await self._sync_frontend_layers()
        except Exception:
            logger.exception("Frontend layer sync failed (non-fatal)")

        return processed

    async def _sync_frontend_layers(self) -> None:
        if settings.ENVIRONMENT == "production":
            # Module layers are baked into the frontend image at build time.
            return

        from .base import BaseModule as _BaseModule
        from .frontend_layers import (
            DEFAULT_FRONTEND_ROOT,
            collect_layers,
            write_modules_json,
        )

        async with self._session_factory() as session:
            installed_names = await ModuleService.installed_names(session)

        installed: list[_BaseModule] = [
            m for m in module_registry.list_discovered() if m.name in installed_names
        ]
        entries = collect_layers(installed)
        write_modules_json(entries, DEFAULT_FRONTEND_ROOT)

    # --- Loading --------------------------------------------------------

    async def _load_pending(self) -> list[ModuleRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ModuleRecord).where(
                    ModuleRecord.state.in_(
                        [
                            ModuleState.TO_INSTALL.value,
                            ModuleState.TO_UPGRADE.value,
                            ModuleState.TO_REMOVE.value,
                        ]
                    )
                )
            )
            return list(result.scalars())

    def _order_pending(self, records: list[ModuleRecord]) -> list[ModuleRecord]:
        """Order the batch: installs dependencies-first, removals dependents-first.

        Removals must run in *reverse* topological order (#286): tearing
        the dependency down first drags the dependent's Alembic branch
        down with it (``depends_on``), so by the time the dependent is
        processed its tables are gone and the ``pg_dump`` backup step
        fails — stranding the record in ``to_remove``. Installs/upgrades
        keep the dependencies-first order and run before removals.
        """

        def topo(recs: list[ModuleRecord]) -> list[ModuleRecord]:
            by_name = {r.name: r for r in recs}
            # Filter unknown deps: a pending record may depend on already-
            # installed modules outside this group — those don't need
            # ordering here.
            return topological_sort(
                recs,
                key=lambda r: r.name,
                deps_of=lambda r: (
                    d
                    for d in ((r.manifest_snapshot or {}).get("depends", []) or [])
                    if d in by_name
                ),
            )

        removals = [r for r in records if r.state == ModuleState.TO_REMOVE.value]
        others = [r for r in records if r.state != ModuleState.TO_REMOVE.value]
        return topo(others) + list(reversed(topo(removals)))

    # --- Dispatch -------------------------------------------------------

    async def _process_one(self, record: ModuleRecord) -> None:
        if record.state == ModuleState.TO_INSTALL.value:
            await self._install(record)
        elif record.state == ModuleState.TO_UPGRADE.value:
            await self._upgrade(record)
        elif record.state == ModuleState.TO_REMOVE.value:
            await self._remove(record)

    # --- Install --------------------------------------------------------

    async def _install(self, record: ModuleRecord) -> None:
        module = module_registry.get(record.name)
        if module is None:
            raise RuntimeError(f"Cannot install {record.name}: not in in-memory registry")

        migrate_log = await self._op_log.started(
            module_name=record.name, operation="install", step="migrate"
        )
        applied_revision = await self._run_migrate(module)
        await self._op_log.completed(migrate_log, {"applied_revision": applied_revision})

        seed_log = await self._op_log.started(
            module_name=record.name, operation="install", step="seed"
        )
        async with self._session_factory() as session:
            seed_files = _resolve_data_files(module)
            if seed_files:
                await load_module_data_files(session, record.name, seed_files)
                await session.commit()
        await self._op_log.completed(seed_log, {"files": len(seed_files)})

        lifecycle_log = await self._op_log.started(
            module_name=record.name, operation="install", step="lifecycle"
        )
        async with self._session_factory() as session:
            ctx = _build_context(record.name, session)
            await module.install(ctx)
            await session.commit()
        await self._op_log.completed(lifecycle_log)

        finalize_log = await self._op_log.started(
            module_name=record.name, operation="install", step="finalize"
        )
        async with self._session_factory() as session:
            db_record = await session.get(ModuleRecord, record.name)
            if db_record is None:
                raise RuntimeError(f"Record {record.name} vanished mid-install")
            now = datetime.now(UTC)
            db_record.state = ModuleState.INSTALLED.value
            db_record.installed_at = db_record.installed_at or now
            db_record.applied_revision = applied_revision
            if db_record.base_revision is None:
                db_record.base_revision = applied_revision
            db_record.last_state_change = now
            db_record.error_message = None
            db_record.error_at = None
            await session.commit()
        await self._op_log.completed(finalize_log)

    # --- Upgrade --------------------------------------------------------

    async def _upgrade(self, record: ModuleRecord) -> None:
        module = module_registry.get(record.name)
        if module is None:
            raise RuntimeError(f"Cannot upgrade {record.name}: not in in-memory registry")

        previous_version = record.manifest_snapshot.get("version", record.version)

        migrate_log = await self._op_log.started(
            module_name=record.name, operation="upgrade", step="migrate"
        )
        applied_revision = await self._run_migrate(module)
        await self._op_log.completed(migrate_log, {"applied_revision": applied_revision})

        seed_log = await self._op_log.started(
            module_name=record.name, operation="upgrade", step="seed"
        )
        async with self._session_factory() as session:
            seed_files = _resolve_data_files(module)
            if seed_files:
                await load_module_data_files(session, record.name, seed_files)
                await session.commit()
        await self._op_log.completed(seed_log, {"files": len(seed_files)})

        post_log = await self._op_log.started(
            module_name=record.name, operation="upgrade", step="lifecycle"
        )
        async with self._session_factory() as session:
            ctx = _build_context(record.name, session)
            await module.post_upgrade(ctx, previous_version)
            await session.commit()
        await self._op_log.completed(post_log)

        finalize_log = await self._op_log.started(
            module_name=record.name, operation="upgrade", step="finalize"
        )
        async with self._session_factory() as session:
            db_record = await session.get(ModuleRecord, record.name)
            if db_record is None:
                raise RuntimeError(f"Record {record.name} vanished mid-upgrade")
            db_record.state = ModuleState.INSTALLED.value
            db_record.applied_revision = applied_revision
            db_record.last_state_change = datetime.now(UTC)
            db_record.error_message = None
            db_record.error_at = None
            await session.commit()
        await self._op_log.completed(finalize_log)

    # --- Uninstall ------------------------------------------------------

    async def _remove(self, record: ModuleRecord) -> None:
        module = module_registry.get(record.name)
        tables = _tables_for(module) if module else []

        backup_log = await self._op_log.started(
            module_name=record.name, operation="uninstall", step="backup"
        )
        backup_path = await self._dump_tables(record.name, tables)
        await self._op_log.completed(
            backup_log, {"backup_path": str(backup_path) if backup_path else None}
        )

        lifecycle_log = await self._op_log.started(
            module_name=record.name, operation="uninstall", step="lifecycle"
        )
        if module is not None:
            async with self._session_factory() as session:
                ctx = _build_context(record.name, session)
                await module.uninstall(ctx)
                await session.commit()
        await self._op_log.completed(lifecycle_log)

        delete_log = await self._op_log.started(
            module_name=record.name, operation="uninstall", step="delete_data"
        )
        async with self._session_factory() as session:
            helper = ExternalIdHelper(session)
            pairs = await helper.purge_for_module(record.name)
            await session.commit()
        await self._op_log.completed(delete_log, {"rows_deleted": len(pairs)})

        migrate_log = await self._op_log.started(
            module_name=record.name, operation="uninstall", step="migrate_down"
        )
        downgrade_target = _downgrade_target_for(record.name, record.base_revision)
        await self._run_downgrade(downgrade_target)
        await self._op_log.completed(migrate_log, {"target_revision": downgrade_target})

        finalize_log = await self._op_log.started(
            module_name=record.name, operation="uninstall", step="finalize"
        )
        async with self._session_factory() as session:
            db_record = await session.get(ModuleRecord, record.name)
            if db_record is None:
                return
            db_record.state = ModuleState.UNINSTALLED.value
            db_record.applied_revision = None
            db_record.installed_at = None
            db_record.last_state_change = datetime.now(UTC)
            db_record.error_message = None
            db_record.error_at = None
            await session.commit()
        await self._op_log.completed(finalize_log)

    # --- External commands ---------------------------------------------

    async def _run_migrate(self, module: BaseModule) -> str | None:
        """Run ``alembic upgrade`` for the module's branch, if any.

        Modules with no Alembic branch (legacy, main linear) don't need
        any migration step — the main chain has already been applied.
        """
        if not _has_branch(module):
            return None
        return _alembic_cmd(["upgrade", f"{module.name}@head"])

    async def _run_downgrade(self, revision: str) -> None:
        _alembic_cmd(["downgrade", revision])

    async def _dump_tables(self, module_name: str, tables: list[str]) -> Path | None:
        if not tables:
            return None

        # Ask Postgres which of the module's tables still exist (#298).
        # This replaces the brittle stderr-string check: a table may be
        # gone because a crash or earlier downgrade already removed it;
        # dumping only survivors avoids pg_dump exit-1 and preserves a
        # partial backup instead of skipping it entirely.
        present = await self._existing_tables(tables)
        remaining = [t for t in tables if t in present]
        if not remaining:
            logger.warning(
                "No tables to back up for module %s (%s); skipping backup",
                module_name,
                ", ".join(tables),
            )
            return None

        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = BACKUP_ROOT / f"module_{module_name}_{timestamp}.sql"

        args = ["pg_dump", "--data-only", "--no-owner", _pg_dump_dsn(settings.DATABASE_URL)]
        for table in remaining:
            args.extend(["--table", table])

        try:
            with target.open("w") as fh:
                # 5 min cap so a locked / oversized table can't hang
                # lifespan startup or an admin-triggered uninstall.
                subprocess.run(args, stdout=fh, stderr=subprocess.PIPE, check=True, timeout=300)
        except subprocess.CalledProcessError as exc:
            target.unlink(missing_ok=True)
            stderr = (exc.stderr or b"").decode(errors="replace")
            raise RuntimeError(
                f"pg_dump failed backing up module {module_name}: {stderr.strip()}"
            ) from exc
        except FileNotFoundError as exc:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"pg_dump not available; cannot back up module {module_name}. "
                "Install postgresql-client in the runtime image."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"pg_dump timed out backing up module {module_name} after "
                f"{exc.timeout}s. Retry once the table is free or grow the cap."
            ) from exc

        if target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            raise RuntimeError(f"pg_dump produced an empty backup for module {module_name}")
        return target

    async def _existing_tables(self, tables: list[str]) -> set[str]:
        """Return the subset of *tables* that exist in the database.

        Uses the asyncpg inspector — the driver the app already ships —
        instead of parsing pg_dump stderr (#298).  The query hits
        ``information_schema.tables`` scoped to the public schema.
        """
        from sqlalchemy import text as sa_text

        async with self._session_factory() as session:
            result = await session.execute(
                sa_text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = ANY(:names)"
                ),
                {"names": list(tables)},
            )
            return {row[0] for row in result.all()}

    # --- Error book-keeping --------------------------------------------

    async def _mark_error(self, module_name: str, message: str) -> None:
        async with self._session_factory() as session:
            record = await session.get(ModuleRecord, module_name)
            if record is None:
                return
            record.error_message = message
            record.error_at = datetime.now(UTC)
            await session.commit()


# --- Module-level helpers -------------------------------------------------


def _resolve_data_files(module: BaseModule) -> list[Path]:
    """Return on-disk paths for ``manifest.data_files`` that exist."""
    manifest = module.get_manifest()
    if not manifest.data_files:
        return []

    import importlib.util

    spec = importlib.util.find_spec(type(module).__module__)
    if spec is None or spec.origin is None:
        return []

    base = Path(spec.origin).parent
    paths: list[Path] = []
    for rel in manifest.data_files:
        candidate = (base / rel).resolve()
        if candidate.exists():
            paths.append(candidate)
        else:
            logger.warning(
                "Seed file %s declared by %s does not exist",
                candidate,
                manifest.name,
            )
    return paths


def _tables_for(module: BaseModule) -> list[str]:
    """Collect ``__tablename__`` values from the module's SQLAlchemy models."""
    tables: list[str] = []
    for model in module.get_models():
        name = getattr(model, "__tablename__", None)
        if name:
            tables.append(str(name))
    return tables


def _build_context(module_name: str, session: AsyncSession) -> ModuleContext:
    from app.core.events import event_bus

    return ModuleContext(
        module_name=module_name,
        db=session,
        event_bus=event_bus,
        logger=logging.getLogger(f"app.modules.{module_name}"),
    )


def _has_branch(module: BaseModule) -> bool:
    """True when the module ships its own Alembic branch directory."""
    import importlib.util

    spec = importlib.util.find_spec(type(module).__module__)
    if spec is None or spec.origin is None:
        return False
    base = Path(spec.origin).parent
    return (base / "migrations" / "versions").is_dir()


def _alembic_cmd(args: list[str]) -> str | None:
    """Run an Alembic command in a subprocess and return the target head.

    Previously this called ``alembic.command.X`` in-process, but our
    ``alembic/env.py`` uses ``asyncio.run()`` to run async migrations —
    which crashes with ``RuntimeError: asyncio.run() cannot be called
    from a running event loop`` when the lifespan invokes it. A
    subprocess gives Alembic a fresh interpreter with no parent loop.

    ``args`` is forwarded verbatim to the ``alembic`` CLI (e.g.
    ``["upgrade", "schedules@head"]`` or ``["downgrade", "base"]``).
    """
    cfg_path = alembic_cfg_path()
    backend_root = cfg_path.parent

    try:
        # 5 min cap per Alembic step. Modules with very long migrations
        # should raise this explicitly rather than silently hanging the
        # lifespan startup.
        subprocess.run(
            ["alembic", "-c", str(cfg_path), *args],
            cwd=str(backend_root),
            check=True,
            timeout=300,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"alembic {' '.join(args)} failed with exit code {exc.returncode}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"alembic {' '.join(args)} timed out after {exc.timeout}s") from exc

    # Resolve the caller's targeted head. Using ``get_current_head`` would
    # raise ``MultipleHeads`` now that schedules has its own branch, so
    # only return a head when the caller specified a branch-qualified
    # target (``<label>@head``). Other callers ignore the return.
    if len(args) >= 2 and args[-1].endswith("@head"):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config(str(cfg_path)))
        return script.get_revision(args[-1]).revision
    return None


def _parent_revision(revision: str) -> str:
    """Return the ``down_revision`` of ``revision``, or ``'base'`` if none."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(alembic_cfg_path())))
    rev = script.get_revision(revision)
    down = rev.down_revision
    if down is None:
        return "base"
    return down if isinstance(down, str) else down[0]


def _module_branch_label(revision: str) -> str | None:
    """Return the Alembic branch label that owns ``revision``.

    Walks from ``revision`` down through its ancestors and returns the
    first explicitly-declared ``branch_labels`` it finds. The module-system
    convention is that a module's first revision carries the label and
    every follow-up in the same module chains off it without a label, so
    walking down from the module's own head lands on that first revision.

    Uses ``_orig_branch_labels`` (the file's own declaration) instead of
    ``branch_labels`` because Alembic propagates labels upward to all
    ancestors of a labelled revision — that propagation would otherwise
    misattribute a main-linear revision to a downstream branch (e.g.
    ``tp_0002`` reported as ``verifactu`` because ``vfy_0001`` chains off
    it).
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(alembic_cfg_path())))
    rev = script.get_revision(revision)
    while rev is not None:
        if rev._orig_branch_labels:
            return next(iter(rev._orig_branch_labels))
        down = rev.down_revision
        if down is None:
            return None
        rev = script.get_revision(down if isinstance(down, str) else down[0])
    return None


def _downgrade_target_for(module_name: str, base_revision: str | None) -> str:
    """Resolve the Alembic target for uninstalling a module.

    - No ``base_revision`` (legacy main-linear module): ``"base"`` — kept
      as a defensive fallback; reconcile now forces those modules to
      ``removable=False`` so this path shouldn't be hit in practice.
    - Revision belongs to a labelled module branch: ``"<label>@-<N>"``
      where ``N`` is the count of revisions the module owns. This is
      the only branch-scoped form Alembic supports: ``<label>@base``
      globally downgrades every branch to the labelled branch's shared
      ancestor, which would cascade into other modules.
    - Revision with no owning label (should not happen post-audit):
      downgrade to the parent revision.
    """
    if not base_revision:
        return "base"
    label = _module_branch_label(base_revision)
    if label is not None:
        count = _count_owned_revisions(module_name)
        if count > 0:
            return f"{label}@-{count}"
        return "base"
    return _parent_revision(base_revision)


def _count_owned_revisions(module_name: str) -> int:
    """Return how many Alembic revisions the module owns.

    Counts ``.py`` files in ``app/modules/<name>/migrations/versions/``
    (excluding ``__init__`` and other non-revision files). Zero when
    the module has no branch of its own.
    """
    modules_root = Path(__file__).resolve().parents[3] / "app" / "modules"
    versions_dir = modules_root / module_name / "migrations" / "versions"
    if not versions_dir.is_dir():
        return 0
    return sum(1 for p in versions_dir.glob("*.py") if not p.name.startswith("__"))


def _pg_dump_dsn(database_url: str) -> str:
    """Strip SQLAlchemy async driver prefix so ``pg_dump`` accepts the URL."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://")
