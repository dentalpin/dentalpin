"""Module registry: what is on disk vs. what is live in this process.

Two sets, deliberately separate (issue #91):

* **discovered** — every module the loader found (entry points + dev
  filesystem scan). The lifecycle machinery (reconcile, install,
  uninstall) needs all of them, whatever their ``core_module.state``.
* **active** — the subset the loader mounted at boot because its state is
  ``installed``: router mounted, event handlers subscribed, tools
  registered. Anything that asks "is module X live?" (RBAC grants,
  scheduler jobs, tenant ``modules_enabled``, feature gates in other
  modules) must use the *active* view.

Activation is a boot-time decision: modules never hot-load, so there is
no ``deactivate``; a restart re-evaluates from the DB.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """In-memory map of discovered modules plus the set of active names."""

    def __init__(self) -> None:
        self._modules: dict[str, BaseModule] = {}
        self._active: set[str] = set()

    # --- discovered -----------------------------------------------------

    def register(self, module: "BaseModule") -> None:
        """Record a discovered module instance (not yet active)."""
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' is already registered")
        from app.core.settings.spec import validate_declarations

        known_permissions = {
            f"{module.name}.{permission}" for permission in module.get_permissions()
        }
        validate_declarations(
            module.name,
            list(module.get_settings()),
            known_permissions=known_permissions,
        )
        self._modules[module.name] = module
        logger.info(f"Registered module: {module.name} v{module.version}")

    def unregister(self, name: str) -> None:
        """Forget a module entirely (tests, fixtures). No-op if unknown."""
        self._modules.pop(name, None)
        if name in self._active:
            self._active.discard(name)
            _invalidate_permissions()

    def get(self, name: str) -> "BaseModule | None":
        """Get a discovered module by name, or None if not found."""
        return self._modules.get(name)

    def is_discovered(self, name: str) -> bool:
        return name in self._modules

    def list_discovered(self) -> list["BaseModule"]:
        """Every discovered module, in registration (topological) order."""
        return list(self._modules.values())

    # --- active ---------------------------------------------------------

    def activate(self, name: str) -> None:
        """Mark a discovered module as live in this process."""
        if name not in self._modules:
            raise ValueError(f"Cannot activate unknown module '{name}'")
        self._active.add(name)
        # The role-permission merge reads the active set; drop its cache so
        # the module's manifest grants apply on next lookup.
        _invalidate_permissions()

    def is_active(self, name: str) -> bool:
        return name in self._active

    def list_active(self) -> list["BaseModule"]:
        """Active modules, in registration (topological) order."""
        return [m for m in self._modules.values() if m.name in self._active]

    def get_all_permissions(self) -> list[str]:
        """Every permission of every *active* module, fully namespaced.

        ``'read'`` declared by module ``patients`` becomes ``'patients.read'``.
        """
        return [
            f"{module.name}.{perm}"
            for module in self.list_active()
            for perm in module.get_permissions()
        ]


def _invalidate_permissions() -> None:
    # Local import: the auth package imports this registry transitively.
    from app.core.auth.permissions import invalidate_role_permissions_cache

    invalidate_role_permissions_cache()


# Global singleton instance
module_registry = ModuleRegistry()
