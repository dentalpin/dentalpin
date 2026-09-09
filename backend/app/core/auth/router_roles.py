"""Clinic-scoped RBAC role management endpoints (issue #46).

Lets an admin list roles, create/edit/delete clinic-custom roles, assign
permissions, and manage per-clinic overrides on the shared system roles. The
DB tables (``roles`` / ``role_permissions`` / ``clinic_role_overrides``) are
the source of truth; :mod:`app.core.auth.rbac` resolves them at check time.

Everything is scoped to the caller's clinic (``ctx.clinic_id``). A caller can
only ever see or mutate roles within the clinic they administer.
"""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugins import module_registry
from app.core.schemas import ApiResponse
from app.database import get_db

from .dependencies import ClinicContext, get_clinic_context, require_permission
from .models import ClinicMembership, ClinicRoleOverride, Permission, Role, RolePermission
from .permissions import CORE_PERMISSIONS, ROLES
from .rbac import invalidate_rbac_cache, resolve_granted_permissions

router = APIRouter(prefix="/roles", tags=["roles"])

#: Custom role names ride the legacy ``clinic_memberships.role`` String(20)
#: column this release (the ``role_id`` FK is the future authority), so a
#: custom role name must stay short enough to be assignable.
ROLE_NAME_MAX_LENGTH = 20


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=ROLE_NAME_MAX_LENGTH)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=ROLE_NAME_MAX_LENGTH)
    description: str | None = None
    permissions: list[str] | None = None


class RoleOverrideUpsert(BaseModel):
    """Replace the clinic's overrides for a system role.

    ``granted`` lists permissions to add in this clinic; ``revoked`` lists
    permissions to remove (relative to the role's default grant set). Any other
    override the clinic previously set for this role is cleared first, so the
    payload is a faithful full-state declaration.
    """

    granted: list[str] = Field(default_factory=list)
    revoked: list[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    id: UUID
    clinic_id: UUID | None
    name: str
    is_system: bool
    description: str | None = None
    # The role's *own* stored grant codes (already namespaced/qualified).
    permissions: list[str] = Field(default_factory=list)
    # Effective grants for the caller's clinic, wildcard-resolved so the UI can
    # render a concrete allow-list without re-expanding ``*``/``module.*``.
    effective_permissions: list[str] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    module: str
    code: str


class RoleOverrideResponse(BaseModel):
    granted: list[str] = Field(default_factory=list)
    revoked: list[str] = Field(default_factory=list)


async def _role_or_404(db: AsyncSession, role_id: UUID, clinic_id: UUID) -> Role:
    role = (
        (
            await db.execute(
                select(Role).where(
                    Role.id == role_id,
                    # System roles are visible to every clinic; custom roles only
                    # to their owner clinic.
                    (Role.clinic_id == clinic_id) | (Role.clinic_id.is_(None)),
                )
            )
        )
        .scalars()
        .first()
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


async def _custom_role_or_404(db: AsyncSession, role_id: UUID, clinic_id: UUID) -> Role:
    role = (
        (await db.execute(select(Role).where(Role.id == role_id, Role.clinic_id == clinic_id)))
        .scalars()
        .first()
    )
    if role is None or role.is_system:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom role not found (or not owned by this clinic)",
        )
    return role


async def _role_permission_codes(db: AsyncSession, role_id: UUID) -> list[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
        .order_by(Permission.code)
    )
    return list((await db.execute(stmt)).scalars())


async def _set_role_permissions(db: AsyncSession, role_id: UUID, codes: list[str]) -> None:
    """Replace a role's permission rows with exactly ``codes``.

    Unknown codes raise 422 (the UI offers codes from the catalog, so a typo is
    a caller bug to surface, not silently ignore). Wildcards (``*``,
    ``module.*``) are stored literally.
    """
    valid: set[str] = set(await _available_permission_codes(db))
    unknown = [c for c in codes if c not in valid]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown permission code(s): {', '.join(unknown)}",
        )

    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for code in codes:
        perm = (
            (await db.execute(select(Permission).where(Permission.code == code))).scalars().first()
        )
        if perm is None:
            # Validated above, but a code can be known (core/registry) with
            # no Permission row yet (seeder hasn't run): fail loudly, never
            # silently drop the grant.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown permission code(s): {code}",
            )
        db.add(RolePermission(id=uuid4(), role_id=role_id, permission_id=perm.id))
    await db.flush()


async def _available_permission_codes(db: AsyncSession) -> list[str]:
    """Every code a caller may grant: catalogued rows + core module codes."""
    perms = (await db.execute(select(Permission.code))).scalars().all()
    return sorted(set(perms) | set(module_registry.get_all_permissions()) | set(CORE_PERMISSIONS))


async def _role_response(
    db: AsyncSession, role: Role, clinic_id: UUID, permissions: list[str] | None = None
) -> RoleResponse:
    if permissions is None:
        permissions = await _role_permission_codes(db, role.id)
    effective = sorted(await resolve_granted_permissions(db, clinic_id, role.name))
    return RoleResponse(
        id=role.id,
        clinic_id=role.clinic_id,
        name=role.name,
        is_system=role.is_system,
        description=role.description,
        permissions=permissions,
        effective_permissions=effective,
    )


@router.get("", response_model=ApiResponse[list[RoleResponse]])
async def list_roles(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.roles.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[RoleResponse]]:
    """List the clinic's roles: the five system roles + any clinic custom roles."""
    rows = (
        (
            await db.execute(
                select(Role).where((Role.clinic_id == ctx.clinic_id) | (Role.clinic_id.is_(None)))
            )
        )
        .scalars()
        .all()
    )
    # System roles first (canonical order), then custom roles by name.
    order = {name: i for i, name in enumerate(ROLES)}
    rows.sort(key=lambda r: (order.get(r.name, 99), r.name))
    result = [await _role_response(db, r, ctx.clinic_id) for r in rows]
    return ApiResponse(data=result)


@router.get("/catalog", response_model=ApiResponse[list[PermissionResponse]])
async def list_permission_catalog(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.roles.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PermissionResponse]]:
    """Return every grantable permission code grouped by its owning module."""
    codes = await _available_permission_codes(db)
    result = [
        PermissionResponse(module=code.split(".", 1)[0] if "." in code else "core", code=code)
        for code in codes
    ]
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[RoleResponse], status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.roles.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RoleResponse]:
    """Create a clinic-custom role with the given permissions."""
    if data.name in ROLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{data.name}' is a system role name; choose another",
        )
    clash = (
        (
            await db.execute(
                select(Role.id).where(Role.clinic_id == ctx.clinic_id, Role.name == data.name)
            )
        )
        .scalars()
        .first()
    )
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{data.name}' already exists in this clinic",
        )

    role = Role(
        id=uuid4(),
        clinic_id=ctx.clinic_id,
        name=data.name,
        is_system=False,
        description=data.description,
    )
    db.add(role)
    await db.flush()
    if data.permissions:
        await _set_role_permissions(db, role.id, data.permissions)
    await db.commit()
    invalidate_rbac_cache()
    return ApiResponse(data=await _role_response(db, role, ctx.clinic_id))


@router.put("/{role_id}", response_model=ApiResponse[RoleResponse])
async def update_role(
    role_id: UUID,
    data: RoleUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.roles.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RoleResponse]:
    """Update a clinic-custom role's name, description and/or permissions."""
    role = await _custom_role_or_404(db, role_id, ctx.clinic_id)
    if data.name is not None and data.name != role.name:
        if data.name in ROLES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{data.name}' is a system role name; choose another",
            )
        clash = (
            (
                await db.execute(
                    select(Role.id).where(
                        Role.clinic_id == ctx.clinic_id, Role.name == data.name, Role.id != role_id
                    )
                )
            )
            .scalars()
            .first()
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{data.name}' already exists in this clinic",
            )
        # Memberships reference the role by name this release, so a rename
        # must follow them or the holders end up with a role that resolves to
        # nothing.
        await db.execute(
            update(ClinicMembership)
            .where(ClinicMembership.clinic_id == ctx.clinic_id, ClinicMembership.role == role.name)
            .values(role=data.name)
        )
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        await _set_role_permissions(db, role.id, data.permissions)
    await db.commit()
    invalidate_rbac_cache()
    return ApiResponse(data=await _role_response(db, role, ctx.clinic_id))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.roles.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a clinic-custom role. Rejected while any member holds it."""
    role = await _custom_role_or_404(db, role_id, ctx.clinic_id)
    assigned = (
        (
            await db.execute(
                select(ClinicMembership.id).where(
                    ClinicMembership.clinic_id == ctx.clinic_id,
                    ClinicMembership.role == role.name,
                )
            )
        )
        .scalars()
        .first()
    )
    if assigned is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role.name}' is assigned to users; reassign them first",
        )
    await db.delete(role)
    await db.commit()
    invalidate_rbac_cache()


@router.put("/{role_id}/overrides", response_model=ApiResponse[RoleOverrideResponse])
async def set_role_overrides(
    role_id: UUID,
    data: RoleOverrideUpsert,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.roles.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RoleOverrideResponse]:
    """Replace the clinic's per-clinic overrides for a system role.

    Only applies to shared system roles; a clinic-custom role already carries
    its full intent in its own ``role_permissions``.
    """
    role = await _role_or_404(db, role_id, ctx.clinic_id)
    if not role.is_system:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Overrides apply to system roles only; edit the custom role's permissions",
        )
    if role.name == "admin" and data.revoked:
        # Revoking ``*`` from admin locks the clinic out of this very API.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The admin role cannot lose grants",
        )

    valid: set[str] = set(await _available_permission_codes(db))
    unknown = [c for c in [*data.granted, *data.revoked] if c not in valid]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown permission code(s): {', '.join(unknown)}",
        )

    # Full-state replace: clear any prior overrides for this role+clinic.
    await db.execute(
        delete(ClinicRoleOverride).where(
            ClinicRoleOverride.clinic_id == ctx.clinic_id,
            ClinicRoleOverride.role_id == role.id,
        )
    )
    for code in data.granted:
        perm = (
            (await db.execute(select(Permission).where(Permission.code == code))).scalars().first()
        )
        if perm is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown permission code(s): {code}",
            )
        db.add(
            ClinicRoleOverride(
                id=uuid4(),
                clinic_id=ctx.clinic_id,
                role_id=role.id,
                permission_id=perm.id,
                granted=True,
            )
        )
    for code in data.revoked:
        perm = (
            (await db.execute(select(Permission).where(Permission.code == code))).scalars().first()
        )
        if perm is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown permission code(s): {code}",
            )
        db.add(
            ClinicRoleOverride(
                id=uuid4(),
                clinic_id=ctx.clinic_id,
                role_id=role.id,
                permission_id=perm.id,
                granted=False,
            )
        )
    await db.flush()
    await db.commit()
    invalidate_rbac_cache()
    return ApiResponse(data=RoleOverrideResponse(granted=data.granted, revoked=data.revoked))
