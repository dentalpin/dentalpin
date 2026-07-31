"""Role-permission mappings for RBAC.

This file is the source of truth ONLY for **core** permissions
(admin.users.*, admin.clinic.*, agents.*). Module-namespaced grants
live in each module's ``manifest.role_permissions`` and are merged in
by :func:`get_role_permissions` at lookup time.

Adding a new module never requires editing this file: declare the
per-role grants in the module's manifest and they flow through
automatically. When a module is uninstalled (and removed from the
in-memory registry), its grants disappear from the merged set.

Future direction: replace the hardcoded core map with a DB-driven
table so clinics can define custom roles per tenant.
"""

from typing import Final

# Valid roles - order matters for UI display
ROLES: Final[list[str]] = [
    "admin",
    "dentist",
    "hygienist",
    "assistant",
    "receptionist",
]

# Roles that imply ``ClinicMembership.is_professional`` at creation.
# The flag — not the role — is what agenda/schedules/treatment_plan
# query, so a solo admin-dentist can be marked professional without
# needing a second account (Telegram report, 2026-07-31).
PROFESSIONAL_ROLES: Final[tuple[str, ...]] = ("dentist", "hygienist")

# Core permissions (not from modules)
CORE_PERMISSIONS: Final[list[str]] = [
    "admin.users.read",
    "admin.users.write",
    "admin.clinic.read",
    "admin.clinic.write",
    # AI agent infrastructure
    "agents.view",
    "agents.supervise",
    "agents.configure",
    "agents.manage",
]

# Role -> core-permission grants. Module-namespaced perms are NOT here;
# they live in each module's ``manifest.role_permissions`` and are
# merged in by ``get_role_permissions``.
ROLE_PERMISSIONS: Final[dict[str, list[str]]] = {
    "admin": ["*"],  # wildcard — matches every namespace, present and future
    "dentist": ["agents.view", "agents.supervise"],
    "hygienist": [],
    "assistant": [],
    "receptionist": [],
}


# Memoized merge of core grants + manifest grants. Cleared whenever the
# in-memory module registry mutates (boot-time module register, future
# install/uninstall hooks).
_role_perms_cache: dict[str, list[str]] = {}


def invalidate_role_permissions_cache() -> None:
    """Drop the cached per-role permission lists. Called by the registry
    when modules are added or removed."""
    _role_perms_cache.clear()


def get_role_permissions(role: str) -> list[str]:
    """Return the full list of granted permissions for ``role``.

    Merges:

    1. The core grants in :data:`ROLE_PERMISSIONS` (admin wildcard,
       core-perm assignments).
    2. ``manifest.role_permissions`` from every module currently in the
       in-memory registry. Entries are prefixed with ``{module_name}.``
       — so a manifest declaring ``{"dentist": ["clinic_hours.read"]}``
       contributes ``"<module>.clinic_hours.read"`` to the dentist role.
    """
    cached = _role_perms_cache.get(role)
    if cached is not None:
        return list(cached)

    base = list(ROLE_PERMISSIONS.get(role, []))
    seen = set(base)

    # Local import to avoid a circular dependency at module-load time:
    # the plugins registry imports auth models transitively.
    from app.core.plugins.manifest import ManifestError
    from app.core.plugins.registry import module_registry

    for module in module_registry.list_modules():
        try:
            manifest = module.get_manifest()
        except ManifestError:
            continue
        module_perms = manifest.role_permissions.get(role, ())
        for perm in module_perms:
            qualified = f"{module.name}.*" if perm == "*" else f"{module.name}.{perm}"
            if qualified not in seen:
                seen.add(qualified)
                base.append(qualified)

    _role_perms_cache[role] = list(base)
    return base


def permission_matches(required: str, granted: str) -> bool:
    """Check if a granted permission satisfies a required permission.

    Supports wildcards:
    - "*" matches everything
    - "module.*" matches "module.resource.action"
    - "module.resource.*" matches "module.resource.action"
    """
    if granted == "*":
        return True

    if granted.endswith(".*"):
        prefix = granted[:-1]  # "clinical.*" -> "clinical."
        return required.startswith(prefix)

    return required == granted


def has_permission(role: str, required_permission: str) -> bool:
    """Check if a role has a specific permission."""
    role_perms = get_role_permissions(role)
    return any(permission_matches(required_permission, perm) for perm in role_perms)


def expand_permissions(role_perms: list[str], all_permissions: list[str]) -> list[str]:
    """Expand wildcards to actual permission list for frontend.

    Frontend needs concrete permissions, not wildcards.
    """
    if "*" in role_perms:
        return all_permissions

    expanded: list[str] = []
    for perm in role_perms:
        if perm.endswith(".*"):
            prefix = perm[:-1]
            expanded.extend(p for p in all_permissions if p.startswith(prefix))
        else:
            expanded.append(perm)

    return list(set(expanded))  # Dedupe
