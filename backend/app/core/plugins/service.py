"""Module service layer.

Thin facade over :class:`ModuleRegistry` + the ``core_module`` tables.
For Etapa 1 this service is read-mostly: it discovers modules, reconciles
the DB, and answers ``list``/``info``/``status``/``doctor`` queries.

Install, uninstall and upgrade flows arrive in Etapa 3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .alembic_paths import resolve_module_branch_head
from .base import BaseModule
from .db_models import ModuleOperationLog, ModuleRecord
from .manifest import Manifest, ManifestError
from .operation_log import LogEntry, log_entry_from_row
from .registry import module_registry
from .state import ModuleCategory, ModuleState
from .topology import MissingDependencyError, topological_sort

logger = logging.getLogger(__name__)


class ModuleOperationError(RuntimeError):
    """Raised by :class:`ModuleService` install/uninstall/upgrade when a
    transition is not allowed (blocked dep, legacy module, etc.)."""


@dataclass
class ModuleInfo:
    """Projection of a module + its DB row for CLI/API output."""

    name: str
    version: str
    installed_version: str | None
    state: ModuleState
    category: ModuleCategory
    removable: bool
    auto_install: bool
    installed_at: datetime | None
    last_state_change: datetime
    base_revision: str | None
    applied_revision: str | None
    error_message: str | None
    error_at: datetime | None
    summary: str
    depends: list[str]
    in_disk: bool
    installable: bool
    upgrade_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "installed_version": self.installed_version,
            "state": self.state.value,
            "category": self.category.value,
            "removable": self.removable,
            "auto_install": self.auto_install,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "last_state_change": self.last_state_change.isoformat(),
            "base_revision": self.base_revision,
            "applied_revision": self.applied_revision,
            "error_message": self.error_message,
            "error_at": self.error_at.isoformat() if self.error_at else None,
            "summary": self.summary,
            "depends": self.depends,
            "in_disk": self.in_disk,
            "installable": self.installable,
            "upgrade_available": self.upgrade_available,
        }


@dataclass
class DoctorReport:
    """Diagnostic output from :meth:`ModuleService.doctor`."""

    orphans: list[str]
    missing_dependencies: list[tuple[str, str]]
    manifest_errors: list[tuple[str, str]]
    errored_modules: list[tuple[str, str]]

    @property
    def ok(self) -> bool:
        return not (
            self.orphans
            or self.missing_dependencies
            or self.manifest_errors
            or self.errored_modules
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "orphans": self.orphans,
            "missing_dependencies": [
                {"module": m, "missing": dep} for m, dep in self.missing_dependencies
            ],
            "manifest_errors": [{"module": m, "error": err} for m, err in self.manifest_errors],
            "errored_modules": [{"module": m, "error": err} for m, err in self.errored_modules],
        }


class ModuleService:
    """Service-layer operations on modules.

    Usage: instantiate per request/CLI invocation with a live session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- Discovery + reconciliation -------------------------------------

    def discovered(self) -> list[BaseModule]:
        """Every module found on disk, whatever its install state."""
        return module_registry.list_discovered()

    async def reconcile_with_db(self) -> None:
        """Ensure ``core_module`` contains one row per discovered module.

        Discovered modules that are new in the DB are inserted as
        ``installed`` when their manifest says ``auto_install=True`` and as
        ``uninstalled`` otherwise; the lifespan mounts the ``installed`` set
        right after this (issue #91). Discovered modules already in the DB
        have their ``version`` + ``manifest_snapshot`` refreshed if the
        version changed.

        Modules present in DB but missing from disk are left alone here
        — :meth:`doctor` surfaces them as orphans.
        """
        discovered = self.discovered()
        existing = await self._load_existing_records()
        now = datetime.now(UTC)

        for module in discovered:
            try:
                manifest = module.get_manifest()
            except ManifestError as exc:
                logger.error(
                    "Skipping reconcile for %s (manifest invalid): %s",
                    module.name,
                    exc,
                )
                continue

            # Resolve the Alembic branch head for modules that ship their
            # own migrations — without this, uninstall cannot safely
            # downgrade because the processor only populates
            # ``base_revision`` during the install flow, which auto-
            # installed modules never go through.
            branch_head = resolve_module_branch_head(module)

            # The branch-isolation invariant for ``removable=True`` is
            # enforced at manifest-validation time (see
            # :mod:`manifest_validator`) — reconcile trusts it.
            record = existing.get(module.name)
            if record is None:
                # Modules with ``auto_install=False`` must wait for an
                # explicit Install action from the admin UI before they
                # become active. They stay ``uninstalled``: discovered, but
                # not mounted — no router, handlers, tools, jobs or grants
                # — and ``base_revision`` is left blank until the user
                # promotes them. Install runs the full processor pipeline
                # (migrate → seed → lifecycle hook → finalize).
                if manifest.auto_install:
                    initial_state = ModuleState.INSTALLED.value
                    initial_installed_at = now
                    initial_base_revision = branch_head
                    initial_applied_revision = branch_head
                else:
                    initial_state = ModuleState.UNINSTALLED.value
                    initial_installed_at = None
                    initial_base_revision = None
                    initial_applied_revision = None

                self.db.add(
                    ModuleRecord(
                        name=manifest.name,
                        version=manifest.version,
                        state=initial_state,
                        category=manifest.category.value,
                        removable=manifest.removable,
                        auto_install=manifest.auto_install,
                        installed_at=initial_installed_at,
                        last_state_change=now,
                        manifest_snapshot=manifest.to_snapshot(),
                        base_revision=initial_base_revision,
                        applied_revision=initial_applied_revision,
                    )
                )
                logger.info(
                    "Reconciled: inserted new module %s (state=%s)",
                    manifest.name,
                    initial_state,
                )
                continue

            if record.version != manifest.version:
                logger.info(
                    "Reconciled: %s installed version %s drifts from disk %s (awaiting upgrade)",
                    manifest.name,
                    record.version,
                    manifest.version,
                )
                # NOTE: record.version intentionally keeps the last-applied
                # version — it is the upgrade signal (see `upgrade()` and
                # `upgrade_available`). Only the upgrade finalize advances it.

            # Always refresh the snapshot so DB stays in sync with disk.
            record.manifest_snapshot = manifest.to_snapshot()
            record.category = manifest.category.value
            record.removable = manifest.removable
            record.auto_install = manifest.auto_install

            # Backfill base_revision for modules reconciled before this
            # logic existed — enables uninstall of already-installed
            # removable modules.
            if record.base_revision is None and branch_head is not None:
                record.base_revision = branch_head
                if record.applied_revision is None:
                    record.applied_revision = branch_head

        await self.db.commit()

    async def _load_existing_records(self) -> dict[str, ModuleRecord]:
        result = await self.db.execute(select(ModuleRecord))
        return {r.name: r for r in result.scalars()}

    @staticmethod
    async def installed_names(db: AsyncSession) -> set[str]:
        """Names of the modules whose ``core_module.state`` is ``installed``.

        The boot sequence mounts exactly this set (issue #91); seeds and
        the frontend-layer sync gate on it too.
        """
        result = await db.execute(
            select(ModuleRecord.name).where(ModuleRecord.state == ModuleState.INSTALLED.value)
        )
        return set(result.scalars())

    # --- Query ----------------------------------------------------------

    async def list_modules(self) -> list[ModuleInfo]:
        """Return combined in-memory + DB view of all known modules."""
        records = await self._load_existing_records()
        discovered = {m.name: m for m in self.discovered()}

        names = sorted(set(records) | set(discovered))
        infos: list[ModuleInfo] = []

        for name in names:
            record = records.get(name)
            module = discovered.get(name)

            manifest = self._safe_manifest(module) if module else None
            summary = manifest.summary if manifest else ""
            depends = (
                list(manifest.depends)
                if manifest
                else list((record.manifest_snapshot or {}).get("depends", []))
            )
            version = manifest.version if manifest else (record.version if record else "")
            category = (
                manifest.category
                if manifest
                else ModuleCategory(record.category)
                if record
                else ModuleCategory.OFFICIAL
            )
            state = ModuleState(record.state) if record else ModuleState.UNINSTALLED

            # `_mark_error` only fires while a pending op is in-flight, so
            # an INSTALLED record carrying `error_message` is stale by
            # construction — hide it from the card.
            stale_error = record is not None and state == ModuleState.INSTALLED
            err_msg = None if stale_error else (record.error_message if record else None)
            err_at = None if stale_error else (record.error_at if record else None)

            infos.append(
                ModuleInfo(
                    name=name,
                    version=version,
                    installed_version=record.version if record else None,
                    state=state,
                    category=category,
                    removable=record.removable if record else True,
                    auto_install=record.auto_install if record else False,
                    installed_at=record.installed_at if record else None,
                    last_state_change=(record.last_state_change if record else datetime.now(UTC)),
                    base_revision=record.base_revision if record else None,
                    applied_revision=record.applied_revision if record else None,
                    error_message=err_msg,
                    error_at=err_at,
                    summary=summary,
                    depends=depends,
                    in_disk=module is not None,
                    installable=(
                        manifest.installable
                        if manifest is not None
                        else (
                            (record.manifest_snapshot or {}).get("installable", True)
                            if record
                            else True
                        )
                    ),
                    upgrade_available=(
                        record is not None
                        and state == ModuleState.INSTALLED
                        and manifest is not None
                        and manifest.version != record.version
                    ),
                )
            )

        return infos

    async def get_info(self, name: str) -> ModuleInfo | None:
        for info in await self.list_modules():
            if info.name == name:
                return info
        return None

    async def status(self) -> dict[str, Any]:
        """Summary: counts by state + list of pending + errored modules."""
        infos = await self.list_modules()
        by_state: dict[str, int] = {}
        pending: list[str] = []
        errored: list[str] = []

        for info in infos:
            by_state[info.state.value] = by_state.get(info.state.value, 0) + 1
            if info.state in {
                ModuleState.TO_INSTALL,
                ModuleState.TO_UPGRADE,
                ModuleState.TO_REMOVE,
            }:
                pending.append(info.name)
            if info.error_message and info.state != ModuleState.INSTALLED:
                errored.append(info.name)

        return {
            "by_state": by_state,
            "pending": pending,
            "errored": errored,
            "total": len(infos),
        }

    async def doctor(self) -> DoctorReport:
        """Run diagnostic checks across discovered + persisted modules."""
        records = await self._load_existing_records()
        discovered = {m.name: m for m in self.discovered()}

        orphans: list[str] = [
            name
            for name, record in records.items()
            if name not in discovered
            and record.state not in (ModuleState.UNINSTALLED.value, ModuleState.DISABLED.value)
        ]

        manifest_errors: list[tuple[str, str]] = []
        for name, module in discovered.items():
            try:
                module.get_manifest()
            except ManifestError as exc:
                manifest_errors.append((name, str(exc)))

        known_names = set(discovered) | set(records)
        missing_deps: list[tuple[str, str]] = []
        for name, module in discovered.items():
            for dep in module.dependencies:
                if dep not in known_names:
                    missing_deps.append((name, dep))

        errored = [
            (name, record.error_message or "")
            for name, record in records.items()
            if record.error_message and record.state != ModuleState.INSTALLED.value
        ]

        return DoctorReport(
            orphans=orphans,
            missing_dependencies=missing_deps,
            manifest_errors=manifest_errors,
            errored_modules=errored,
        )

    async def operation_log(self, name: str, *, limit: int = 20) -> list[LogEntry]:
        """Return the most recent log entries for ``name`` (desc by id).

        Raises :class:`ModuleOperationError` if the module is unknown to
        the DB. ``limit`` is clamped by the caller.
        """
        records = await self._load_existing_records()
        if name not in records:
            raise ModuleOperationError(f"Unknown module: '{name}'")

        result = await self.db.execute(
            select(ModuleOperationLog)
            .where(ModuleOperationLog.module_name == name)
            .order_by(ModuleOperationLog.id.desc())
            .limit(limit)
        )
        return [log_entry_from_row(row) for row in result.scalars()]

    async def orphan(self, name: str) -> bool:
        """Mark a missing-from-disk module as ``uninstalled`` for recovery."""
        record = (
            await self.db.execute(select(ModuleRecord).where(ModuleRecord.name == name))
        ).scalar_one_or_none()
        if record is None:
            return False

        record.state = ModuleState.UNINSTALLED.value
        record.last_state_change = datetime.now(UTC)
        record.error_message = None
        record.error_at = None
        await self.db.commit()
        return True

    # --- State transitions (no execution; processor handles that) -------

    async def install(self, name: str, *, force: bool = False) -> list[str]:
        """Mark ``name`` and every uninstalled dep as ``to_install``.

        Returns the ordered list of module names scheduled (topo order),
        including transitive dependencies. Caller is expected to trigger
        a restart — the lifespan processor executes pending operations.
        """
        module = self._require_discovered(name)
        manifest = module.get_manifest()
        if not manifest.installable and not force:
            raise ModuleOperationError(f"Module '{name}' is marked installable=False")

        records = await self._load_existing_records()
        chain = self._dependency_chain(name)
        scheduled: list[str] = []
        now = datetime.now(UTC)

        for dep_name in chain:
            dep_module = self._require_discovered(dep_name)
            dep_manifest = dep_module.get_manifest()
            record = records.get(dep_name)

            if record is None:
                self.db.add(
                    ModuleRecord(
                        name=dep_manifest.name,
                        version=dep_manifest.version,
                        state=ModuleState.TO_INSTALL.value,
                        category=dep_manifest.category.value,
                        removable=dep_manifest.removable,
                        auto_install=dep_manifest.auto_install,
                        last_state_change=now,
                        manifest_snapshot=dep_manifest.to_snapshot(),
                    )
                )
                scheduled.append(dep_name)
                continue

            if record.state == ModuleState.INSTALLED.value:
                continue
            if record.state in {
                ModuleState.TO_INSTALL.value,
                ModuleState.TO_UPGRADE.value,
            }:
                continue

            record.state = ModuleState.TO_INSTALL.value
            record.version = dep_manifest.version
            record.manifest_snapshot = dep_manifest.to_snapshot()
            record.category = dep_manifest.category.value
            record.removable = dep_manifest.removable
            record.auto_install = dep_manifest.auto_install
            record.last_state_change = now
            record.error_message = None
            record.error_at = None
            scheduled.append(dep_name)

        await self.db.commit()
        return scheduled

    async def uninstall(self, name: str, *, force: bool = False) -> None:
        """Mark ``name`` as ``to_remove`` unless blocked.

        Blocked scenarios:

        * module is ``removable=False`` (official modules) and
          ``force`` is not set.
        * another installed module declares ``name`` in its ``depends``
          — reverse-dep. Unless ``force``.
        * module has no Alembic ``base_revision`` (Fase A legacy) —
          its schema is part of main linear and cannot be cleanly
          unwound. Always blocked, even with ``force``.
        """
        records = await self._load_existing_records()
        record = records.get(name)
        if record is None:
            raise ModuleOperationError(f"Unknown module: '{name}'")

        if record.state == ModuleState.UNINSTALLED.value:
            return  # no-op

        if record.base_revision is None:
            raise ModuleOperationError(
                f"Module '{name}' has no Alembic branch (legacy in main linear). "
                "Uninstall is not supported in Fase A."
            )

        if not record.removable and not force:
            raise ModuleOperationError(
                f"Module '{name}' is marked removable=False. Use force=True to override."
            )

        dependents = [
            other.name
            for other in records.values()
            if other.state
            in {
                ModuleState.INSTALLED.value,
                ModuleState.TO_INSTALL.value,
                ModuleState.TO_UPGRADE.value,
            }
            and name in (other.manifest_snapshot or {}).get("depends", [])
        ]
        if dependents and not force:
            raise ModuleOperationError(
                f"Cannot uninstall '{name}' — required by: {dependents}. "
                "Uninstall them first or pass force=True."
            )

        record.state = ModuleState.TO_REMOVE.value
        record.last_state_change = datetime.now(UTC)
        record.error_message = None
        record.error_at = None
        await self.db.commit()

    async def upgrade(self, name: str) -> bool:
        """Mark ``name`` as ``to_upgrade`` when the on-disk manifest
        version differs from the stored version.

        Returns ``True`` if an upgrade was scheduled, ``False`` if the
        module is already at the declared version.
        """
        module = self._require_discovered(name)
        manifest = module.get_manifest()
        record = (
            await self.db.execute(select(ModuleRecord).where(ModuleRecord.name == name))
        ).scalar_one_or_none()
        if record is None:
            raise ModuleOperationError(f"Unknown module: '{name}'")
        if record.state != ModuleState.INSTALLED.value:
            raise ModuleOperationError(
                f"Cannot upgrade '{name}' from state {record.state}. "
                "Only installed modules can be upgraded."
            )

        if record.version == manifest.version:
            return False

        # NOTE: record.version intentionally keeps the last-APPLIED
        # version here. Only the upgrade finalize advances it, so a
        # failed upgrade still reports upgrade_available and
        # post_upgrade receives the true previous version.
        record.state = ModuleState.TO_UPGRADE.value
        record.manifest_snapshot = manifest.to_snapshot()
        record.last_state_change = datetime.now(UTC)
        record.error_message = None
        record.error_at = None
        await self.db.commit()
        return True

    # --- Helpers --------------------------------------------------------

    def _require_discovered(self, name: str) -> BaseModule:
        module = module_registry.get(name)
        if module is None:
            raise ModuleOperationError(f"Module '{name}' is not discovered; cannot operate on it.")
        return module

    def _dependency_chain(self, name: str) -> list[str]:
        """Return module + every transitive dep in topo order (deps first)."""
        # Walk the transitive closure first so topological_sort sees the
        # full set of items it needs to order.
        closure: dict[str, BaseModule] = {}
        stack = [name]
        while stack:
            current_name = stack.pop()
            if current_name in closure:
                continue
            module = module_registry.get(current_name)
            if module is None:
                raise ModuleOperationError(
                    f"Missing dependency '{current_name}' (required by '{name}')"
                )
            closure[current_name] = module
            stack.extend(module.dependencies)

        try:
            ordered = topological_sort(
                closure.values(),
                key=lambda m: m.name,
                deps_of=lambda m: m.dependencies,
            )
        except MissingDependencyError as exc:
            raise ModuleOperationError(str(exc)) from exc
        return [m.name for m in ordered]

    # --- Helpers --------------------------------------------------------

    @staticmethod
    def _safe_manifest(module: BaseModule) -> Manifest | None:
        try:
            return module.get_manifest()
        except ManifestError as exc:
            logger.error("Manifest error for %s: %s", module.name, exc)
            return None
