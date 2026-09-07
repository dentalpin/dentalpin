"""DB-backed RBAC resolution (issue #46).

Provides clinic-aware permission lookup backed by the ``roles``,
``permissions``, ``role_permissions``, ``module_default_role_permissions``
and ``clinic_role_overrides`` tables, replacing the static ``ROLE_PERMISSIONS``
grant map as the source of truth.

Resolution rule (effective grant set for a membership):

1. **Base** — the system role's ``role_permissions`` rows (seeded from the
   module manifests at seeder time).
2. **Overrides** — any ``clinic_role_overrides`` rows for that role + clinic:
   ``granted=true`` adds a permission, ``granted=false`` removes it.
3. **Custom roles** (``clinic_id IS NOT NULL``) express their full intent via
   ``role_permissions`` directly; no system base + override crack open.

Wildcards (``*``, ``module.*``) are stored literally and resolved per-check
via :func:`permission_matches`, mirroring the legacy semantics so the
frontend ``/me`` contract and existing behavior are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from .models import (
    ClinicRoleOverride,
    Permission,
    Role,
    RolePermission,
)
from .permissions import get_role_permissions, has_permission, permission_matches

#: 5 standard roles seeded as system roles (clinic_id IS NULL).
SYSTEM_ROLE_NAMES: tuple[str, ...] = (
    "admin",
    "dentist",
    "hygienist",
    "assistant",
    "receptionist",
)


@dataclass
class ResolvedRole:
    """A role's effective, wildcard-resolved, clinic-scoped permission set."""

    role: str
    role_id: str
    clinic_id: str | None
    granted: set[str] = field(default_factory=set)

    def permits(self, permission: str) -> bool:
        if "*" in self.granted:
            return True
        return any(permission_matches(permission, p) for p in self.granted)


class _RoleSetCache:
    """Per-process, TTL-less cache keyed by (clinic_id, role_name).

    Cleared whenever a role/permission/override mutates (``invalidate``).
    Falls back to a DB read on a miss; correct even if the cache is cold.
    """

    _cache: dict[tuple[UUID | None, str], set[str]]

    def __init__(self) -> None:
        self._cache = {}

    def get(self, clinic_id: UUID | None, role_name: str) -> set[str] | None:
        return self._cache.get((clinic_id, role_name))

    def put(self, clinic_id: UUID | None, role_name: str, granted: set[str]) -> None:
        self._cache[(clinic_id, role_name)] = granted

    def invalidate(self) -> None:
        self._cache.clear()


_role_set_cache = _RoleSetCache()


def invalidate_rbac_cache() -> None:
    _role_set_cache.invalidate()


async def _load_role(db: AsyncSession, clinic_id: UUID | None, role_name: str) -> Role | None:
    stmt = select(Role).where(Role.name == role_name)
    if clinic_id is None:
        stmt = stmt.where(Role.clinic_id.is_(None))
    else:
        # A custom role for this clinic takes precedence; fall back to the
        # system role so a membership can still resolve without an override.
        stmt = stmt.where((Role.clinic_id == clinic_id) | (Role.clinic_id.is_(None))).order_by(
            (Role.clinic_id.is_(None)).asc()
        )
    return (await db.execute(stmt)).scalars().first()


async def _role_granted_permissions(db: AsyncSession, role: Role) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
    )
    return set((await db.execute(stmt)).scalars())


async def _apply_clinic_overrides(
    db: AsyncSession, clinic_id: UUID, role_id: UUID, base: set[str]
) -> set[str]:
    stmt = (
        select(Permission.code, ClinicRoleOverride.granted)
        .join(ClinicRoleOverride, ClinicRoleOverride.permission_id == Permission.id)
        .where(
            ClinicRoleOverride.clinic_id == clinic_id,
            ClinicRoleOverride.role_id == role_id,
        )
    )
    rows = (await db.execute(stmt)).all()
    effective = set(base)
    for code, granted in rows:
        if granted:
            effective.add(code)
        else:
            effective.discard(code)
    return effective


async def resolve_granted_permissions(
    db: AsyncSession, clinic_id: UUID | None, role_name: str
) -> set[str]:
    """Return the effective granted permission set (wildcards excluded) for a
    role in a clinic. ``clinic_id`` may be ``None`` to resolve the pure system
    default (no clinic overrides)."""
    cache_key = (clinic_id, role_name)
    cached = _role_set_cache.get(*cache_key)
    if cached is not None:
        return cached

    role = await _load_role(db, clinic_id, role_name)
    if role is None:
        return set()
    granted = await _role_granted_permissions(db, role)
    if clinic_id is not None:
        granted = await _apply_clinic_overrides(db, clinic_id, role.id, granted)

    _role_set_cache.put(*cache_key, granted)
    return granted


async def has_permission_in_clinic(
    db: AsyncSession, clinic_id: UUID | None, role_name: str, permission: str
) -> bool:
    """True if a membership with ``role_name`` in ``clinic_id`` holds
    ``permission`` (wildcards honoured)."""
    granted = await resolve_granted_permissions(db, clinic_id, role_name)
    if "*" in granted:
        return True
    return any(permission_matches(permission, g) for g in granted)


async def resolve_role_id(db: AsyncSession, clinic_id: UUID | None, role_name: str) -> UUID | None:
    """PK of the ``roles`` row a membership with ``role_name`` should point
    at (clinic-custom role first, system role as fallback). ``None`` when no
    row exists — callers leave ``role_id`` null and the string ``role``
    column remains the read path."""
    role = await _load_role(db, clinic_id, role_name)
    return role.id if role is not None else None


async def granted_permissions_for(
    db: AsyncSession, clinic_id: UUID | None, role_name: str
) -> list[str]:
    """Effective permission codes for a role, honouring ``RBAC_FROM_DB``.

    Single flag-aware entry point for every non-``require_permission``
    caller (routers, services, agent contexts): DB resolution when the
    flag is on, the static merged map otherwise. Dropping the flag later
    is a one-line change here."""
    if settings.RBAC_FROM_DB:
        return sorted(await resolve_granted_permissions(db, clinic_id, role_name))
    return get_role_permissions(role_name)


async def has_permission_for(
    db: AsyncSession, clinic_id: UUID | None, role_name: str, permission: str
) -> bool:
    """Flag-aware single-permission check. Same contract as
    :func:`has_permission`, clinic-scoped when ``RBAC_FROM_DB`` is on."""
    if settings.RBAC_FROM_DB:
        return await has_permission_in_clinic(db, clinic_id, role_name, permission)
    return has_permission(role_name, permission)
