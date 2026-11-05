"""Generic settings API (ADR 0042)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context
from app.core.auth.rbac import has_permission_for
from app.core.schemas import ApiResponse
from app.core.settings.schemas import (
    ModuleSettingsResponse,
    ModuleSettingsUpdate,
    SettingDeclaration,
)
from app.core.settings.service import (
    ClinicSettingsService,
    SettingsClinicNotFoundError,
    UnknownSettingError,
    UnknownSettingsModuleError,
)
from app.core.settings.spec import SettingSpec, SettingValueError
from app.database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


def _not_found(module: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No settings declared for module '{module}'",
    )


async def _declaration(
    db: AsyncSession,
    ctx: ClinicContext,
    spec: SettingSpec,
) -> SettingDeclaration | None:
    if not await has_permission_for(db, ctx.clinic_id, ctx.role, spec.permission):
        return None
    writable = await has_permission_for(
        db, ctx.clinic_id, ctx.role, spec.effective_write_permission
    )
    return SettingDeclaration(
        key=spec.key,
        type=spec.type,
        default=spec.default,
        writable=writable,
        label_key=spec.label_key,
        description_key=spec.description_key,
        choices=list(spec.choices),
        min_value=spec.min_value,
        max_value=spec.max_value,
        max_length=spec.max_length,
        multiline=spec.multiline,
        nullable=spec.nullable,
    )


async def _response(
    db: AsyncSession,
    ctx: ClinicContext,
    module: str,
    specs: list[SettingSpec],
    values: dict[str, Any],
) -> ModuleSettingsResponse:
    declarations: list[SettingDeclaration] = []
    visible: dict[str, Any] = {}
    for spec in specs:
        declaration = await _declaration(db, ctx, spec)
        if declaration is None:
            continue
        declarations.append(declaration)
        visible[spec.key] = values[spec.key]
    return ModuleSettingsResponse(module=module, settings=declarations, values=visible)


@router.get("/{module}", response_model=ApiResponse[ModuleSettingsResponse])
async def get_module_settings(
    module: str,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ModuleSettingsResponse]:
    """Return the readable declarations and effective values of a module.

    Access is per declaration: the route requires clinic membership and
    filters both declarations and values through each spec's permission.
    """
    try:
        specs = ClinicSettingsService.declarations(module)
        values = await ClinicSettingsService.get_values(db, ctx.clinic_id, module)
    except UnknownSettingsModuleError as exc:
        raise _not_found(module) from exc
    except SettingsClinicNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found"
        ) from exc
    return ApiResponse(data=await _response(db, ctx, module, specs, values))


@router.patch("/{module}", response_model=ApiResponse[ModuleSettingsResponse])
async def update_module_settings(
    module: str,
    data: ModuleSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ModuleSettingsResponse]:
    """Update declared settings; every field enforces read and write permissions."""
    try:
        specs = ClinicSettingsService.declarations(module)
    except UnknownSettingsModuleError as exc:
        raise _not_found(module) from exc

    if not data.values:
        try:
            values = await ClinicSettingsService.get_values(db, ctx.clinic_id, module)
        except SettingsClinicNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found"
            ) from exc
        return ApiResponse(data=await _response(db, ctx, module, specs, values))

    by_key = {spec.key: spec for spec in specs}
    for key in data.values:
        spec = by_key.get(key)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown setting for '{module}': {key}",
            )
        if not await has_permission_for(db, ctx.clinic_id, ctx.role, spec.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {spec.permission}",
            )
        if not await has_permission_for(
            db, ctx.clinic_id, ctx.role, spec.effective_write_permission
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {spec.effective_write_permission}",
            )

    try:
        values = await ClinicSettingsService.update(db, ctx.clinic_id, module, data.values)
    except UnknownSettingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except SettingValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except SettingsClinicNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found"
        ) from exc

    return ApiResponse(data=await _response(db, ctx, module, specs, values))
