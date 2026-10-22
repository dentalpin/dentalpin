"""Base module abstract class for the plugin system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import APIRouter
from sqlalchemy.orm import DeclarativeBase

from app.core.settings.spec import SettingSpec

from .manifest import Manifest

if TYPE_CHECKING:
    from app.core.agents.base import BaseAgent
    from app.core.agents.tools.tool import Tool
    from app.core.erasure.types import ErasureContributor
    from app.core.scheduling import ScheduledJob

    from .context import ModuleContext


class BaseModule(ABC):
    """Abstract base class that all modules must inherit from.

    Each module is a self-contained feature that provides:
    - SQLAlchemy models
    - FastAPI router
    - Event handlers (optional)
    - RBAC permissions (optional)
    - AI agent tools (optional)
    - Lifecycle hooks (optional: install, uninstall, post_upgrade)

    Modules declare metadata through a class-level ``manifest`` dict with at
    least ``name`` and ``version``. The dict is the single source of truth
    for identity and policy — :meth:`get_manifest` parses it via
    :meth:`Manifest.from_dict`, which raises :class:`ManifestError` on
    missing required keys.
    """

    manifest: ClassVar[dict[str, Any]] = {}

    # --- Identity (read directly from the manifest dict) ----------------

    @property
    def name(self) -> str:
        return str(self.manifest["name"])

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @property
    def dependencies(self) -> list[str]:
        return list(self.manifest.get("depends") or [])

    # --- Core contract ---------------------------------------------------

    @abstractmethod
    def get_models(self) -> list[type[DeclarativeBase]]:
        """Return SQLAlchemy models to register with the database."""

    @abstractmethod
    def get_router(self) -> APIRouter:
        """Return FastAPI router to mount at ``/api/v1/{module_name}/``."""

    def get_event_handlers(self) -> dict[str, Callable[..., Any]]:
        """Return map of event_name -> handler function.

        Handlers receive event data as a dict (and optionally a DB session
        when async). They should not return anything.
        """
        return {}

    def get_permissions(self) -> list[str]:
        """Return custom permissions this module adds to RBAC.

        Format: ``'resource.action'`` (no module prefix). The registry
        namespaces them automatically, e.g. ``'patients.read'`` from
        ``clinical`` becomes ``'clinical.patients.read'``.
        """
        return []

    # --- Settings contract (ADR 0042) ------------------------------------

    def get_settings(self) -> list[SettingSpec]:
        """Return simple clinic-scoped settings this module declares.

        Default is an empty list. Declarations are validated when the
        module is registered and served through
        ``/api/v1/settings/{module}``; values are stored under
        ``clinics.settings[<module>]``. Never declare credentials here -
        ``clinics.settings`` is returned to clients.
        """
        return []

    # --- AI agent contract ----------------------------------------------

    def get_tools(self) -> list[Tool]:
        """Return callable actions this module exposes to AI agents.

        Default is an empty list. Tool names are namespaced automatically:
        a tool named ``create_appointment`` from module ``agenda`` is
        registered as ``agenda.create_appointment`` in the global
        :class:`~app.core.agents.tools.registry.ToolRegistry`. See
        ``docs/technical/creating-modules.md`` for the full contract.
        """
        return []

    def get_agents(self) -> list[type[BaseAgent]]:
        """Return :class:`~app.core.agents.base.BaseAgent` subclasses
        this module registers.

        Default is an empty list. Override only if the module ships
        agents itself (as opposed to merely exposing tools).
        """
        return []

    # --- Background jobs -------------------------------------------------

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        """Return periodic jobs this module wants the scheduler to run.

        Default is an empty list. The scheduler registers jobs only for
        *active* modules (installed and mounted at boot), so the scheduler
        no longer imports module task functions directly. See
        :class:`~app.core.scheduling.ScheduledJob`.
        """
        return []

    # --- GDPR erasure contract (ADR 0038, issue #546) ---------------------

    def get_erasure_contributors(self) -> list[ErasureContributor]:
        """Return this module's GDPR erasure contributors, if it holds
        subject copies.

        Default is an empty list. The loader collects contributors from the
        *active* modules into
        :class:`~app.core.erasure.registry.SubjectErasureRegistry`, and
        ``gdpr`` pulls them inside the erasure transaction. A contributor
        redacts its own copies and reports its own
        :class:`~app.core.erasure.types.ErasureCoverage` — ``gdpr`` never
        imports contributor modules, and contributors never depend on
        ``gdpr``. See ``docs/technical/creating-modules.md``.
        """
        return []

    # --- Lifecycle hooks (v1 defaults are no-ops) ------------------------

    def on_activate(self) -> None:
        """Called once per boot, right after this module was mounted.

        Runs **only when the module is installed** (``core_module.state``),
        after its router, event handlers and tools are wired. Use it for
        in-memory, cross-module registrations that must be re-attached on
        every restart — compliance hooks, channel adapters. Sync, no DB.
        There is no counterpart: a module that is not installed on the
        next boot is simply never activated (modules never hot-unload).
        """

    async def install(self, ctx: ModuleContext) -> None:
        """Called on first install after migrations ran.

        Typical use: load ``data/*.yaml`` seed files, provision data.
        """

    async def uninstall(self, ctx: ModuleContext) -> None:
        """Called before Alembic downgrade and data removal.

        Typical use: clean up external resources, stop background tasks.
        """

    async def post_upgrade(self, ctx: ModuleContext, from_version: str) -> None:
        """Called after migrations when upgrading to a newer version.

        Typical use: re-run seeds with new ``noupdate`` flags, backfill.
        """

    # --- Manifest accessor ----------------------------------------------

    def get_manifest(self) -> Manifest:
        """Return the parsed manifest. Raises ``ManifestError`` when the
        ``manifest`` class attribute is missing required keys."""
        return Manifest.from_dict(self.manifest)
