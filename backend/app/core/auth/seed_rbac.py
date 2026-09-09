"""Idempotent seeder that persists RBAC into the ``roles``/``permissions``
tables (issue #46).

It reproduces exactly the grant set the legacy static :data:`ROLE_PERMISSIONS`
+ ``manifest.role_permissions`` merge produced (via
:func:`app.core.auth.permissions.get_role_permissions`), so the DB becomes a
faithful drop-in source of truth. Safe to run on every boot and after any
module install/uninstall:

- ``permissions`` gains a row per core permission and per active module's
  :meth:`~app.core.plugins.base.BaseModule.get_permissions` (fully
  namespaced, wildcards stored literally).
- System roles (``clinic_id IS NULL``) get their ``role_permissions`` rows
  reconciled to the computed grant set (add missing, drop stale).
- Each binding is also recorded in ``module_default_role_permissions`` as its
  declared origin, so a reconcile can tell core grants from module grants.

The runtime only reads ``role_permissions`` (plus per-clinic
:class:`~app.core.auth.models.ClinicRoleOverride`); the other tables are the
seeder's bookkeeping.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugins.manifest import ManifestError
from app.core.plugins.registry import module_registry

from .models import (
    ModuleDefaultRolePermission,
    Permission,
    Role,
    RolePermission,
)
from .permissions import CORE_PERMISSIONS, ROLE_PERMISSIONS

logger = logging.getLogger(__name__)


async def _article_permission(db: AsyncSession, module: str, code: str) -> Permission:
    """Fetch an existing permission row or insert it (by unique ``code``)."""
    perm = (await db.execute(select(Permission).where(Permission.code == code))).scalars().first()
    if perm is None:
        perm = Permission(id=uuid4(), module=module, code=code)
        db.add(perm)
        await db.flush()
    return perm


async def _ensure_system_roles(db: AsyncSession) -> dict[str, Role]:
    existing = (await db.execute(select(Role).where(Role.clinic_id.is_(None)))).scalars().all()
    by_name = {r.name: r for r in existing}
    for name in ROLE_PERMISSIONS:
        if name not in by_name:
            role = Role(id=uuid4(), clinic_id=None, name=name, is_system=True)
            db.add(role)
            by_name[name] = role
    await db.flush()
    return by_name


async def _catalogue(db: AsyncSession, roles: dict[str, Role]) -> dict[str, tuple[str, Permission]]:
    """Insert/refresh permission rows. Returns ``{code: (module, Permission)}``."""
    found: dict[str, tuple[str, Permission]] = {}

    def add(module: str, code: str) -> None:
        if code in found:
            return
        found[code] = (module, code)  # placeholder; resolved in second pass

    # Core permissions + the admin wildcard.
    for code in [*CORE_PERMISSIONS, "*"]:
        add("core", code)
    # Every active module's exposed permissions AND every code a manifest can
    # grant (a manifest may grant a ``<module>.*`` wildcard even when the
    # module's ``get_permissions()`` exposes only concrete codes). Both must be
    # catalogued so ``_computed_grant_set`` never references a missing row.
    for module in module_registry.list_active():
        name = module.name
        try:
            manifest = module.get_manifest()
        except ManifestError:
            manifest = None
            # Fall back to get_permissions() only.
        for raw in module.get_permissions():
            add(name, f"{name}.*" if raw == "*" else f"{name}.{raw}")
        if manifest is not None:
            for role_grants in manifest.role_permissions.values():
                for grant in role_grants:
                    add(name, f"{name}.*" if grant == "*" else f"{name}.{grant}")

    # Persist each unique code (safe: unique on ``code``).
    for code in found:
        module = found[code][0]
        perm = await _article_permission(db, module, code)
        found[code] = (module, perm)
    return found


def _computed_grant_set(role: str) -> list[str]:
    """Legacy grant set for a system role: core grants + every active module's
    manifest grants, fully qualified."""
    granted: list[str] = []
    seen: set[str] = set()
    for perm in ROLE_PERMISSIONS.get(role, ()):
        if perm not in seen:
            seen.add(perm)
            granted.append(perm)
    for module in module_registry.list_active():
        try:
            manifest = module.get_manifest()
        except ManifestError:
            continue
        for perm in manifest.role_permissions.get(role, ()):
            qualified = f"{module.name}.*" if perm == "*" else f"{module.name}.{perm}"
            if qualified not in seen:
                seen.add(qualified)
                granted.append(qualified)
    return granted


async def _reconcile_role(
    db: AsyncSession,
    role: Role,
    found: dict[str, tuple[str, Permission]],
) -> None:
    target_ids = {str(found[c][1].id) for c in _computed_grant_set(role.name)}

    existing = (
        (await db.execute(select(RolePermission).where(RolePermission.role_id == role.id)))
        .scalars()
        .all()
    )
    existing_by_perm = {str(rp.permission_id): rp for rp in existing}

    for code, (module, perm) in found.items():
        pid = str(perm.id)
        in_target = pid in target_ids
        row = existing_by_perm.get(pid)
        if in_target and row is None:
            db.add(RolePermission(id=uuid4(), role_id=role.id, permission_id=perm.id))
            await _record_module_default(db, role, module, perm)
        elif not in_target and row is not None:
            await db.delete(row)

    await db.flush()


async def _record_module_default(
    db: AsyncSession, role: Role, module: str, perm: Permission
) -> None:
    stmt = select(ModuleDefaultRolePermission).where(
        ModuleDefaultRolePermission.module == module,
        ModuleDefaultRolePermission.role == role.name,
        ModuleDefaultRolePermission.permission_id == perm.id,
    )
    if (await db.execute(stmt)).scalars().first() is None:
        db.add(
            ModuleDefaultRolePermission(
                id=uuid4(), module=module, role=role.name, permission_id=perm.id
            )
        )


async def seed_rbac(db: AsyncSession) -> None:
    """Reconcile the persisted RBAC with the live module set. Call on boot and
    after module install/uninstall. Idempotent."""
    from .rbac import invalidate_rbac_cache

    roles = await _ensure_system_roles(db)
    found = await _catalogue(db, roles)

    for role in roles.values():
        await _reconcile_role(db, role, found)

    await db.commit()
    invalidate_rbac_cache()

    logger.info(
        "RBAC seeded: %d permission rows, %d system roles",
        len(found),
        len(roles),
    )
