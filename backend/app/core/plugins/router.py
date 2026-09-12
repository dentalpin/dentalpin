"""HTTP endpoints for module management.

Mirror of the CLI, exposed so UI clients can trigger the same state
transitions. The heavy lifting happens at the next backend restart —
every mutating endpoint responds ``202 Accepted`` with a "restart
required" message and the list of modules that would be touched.

Routes are mounted at ``/api/v1/modules``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    block_in_demo,
    get_clinic_context,
    require_permission,
)
from app.core.auth.permissions import permission_matches
from app.core.auth.rbac import granted_permissions_for
from app.core.schemas import ApiResponse
from app.database import get_db

from .registry import module_registry
from .service import ModuleOperationError, ModuleService
from .state import ModuleState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/modules", tags=["modules"])


# --- Read endpoints ------------------------------------------------------


@router.get("")
async def list_modules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[list[dict[str, Any]]]:
    svc = ModuleService(db)
    infos = await svc.list_modules()
    return ApiResponse(data=[info.to_dict() for info in infos])


@router.get("/{name}")
async def get_module(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[dict[str, Any]]:
    svc = ModuleService(db)
    info = await svc.get_info(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Module not found: {name}")
    return ApiResponse(data=info.to_dict())


@router.get("/-/status")
async def module_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[dict[str, Any]]:
    svc = ModuleService(db)
    return ApiResponse(data=await svc.status())


@router.get("/-/active")
async def active_modules(
    db: Annotated[AsyncSession, Depends(get_db)],
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
) -> ApiResponse[list[dict[str, Any]]]:
    """Modules that are ``installed`` *and* mounted in this process, with
    the nav items visible to the caller.

    This is the frontend's source of truth for the sidebar. Every
    authenticated user may read it; navigation entries are filtered by
    the caller's role-based permissions so the response is already
    tailored to what the UI should render. The registry check keeps the
    UI honest when a module is ``installed`` in the DB but the loader
    skipped it (a dependency was force-uninstalled).
    """
    svc = ModuleService(db)
    active: list[dict[str, Any]] = []
    # Resolve the caller's grant set once (flag-aware); per-item matching
    # below is in-memory so nav filtering stays a single DB round-trip.
    granted = await granted_permissions_for(db, ctx.clinic_id, ctx.role)

    for info in await svc.list_modules():
        if info.state != ModuleState.INSTALLED or not module_registry.is_active(info.name):
            continue

        module = svc.discovered()
        manifest = next((m.get_manifest() for m in module if m.name == info.name), None)
        if manifest is None:
            continue

        nav = list(manifest.frontend.get("navigation") or [])
        filtered_nav = [item for item in nav if _nav_visible(item, granted)]

        active.append(
            {
                "name": manifest.name,
                "version": manifest.version,
                "category": manifest.category.value,
                "summary": manifest.summary,
                "navigation": filtered_nav,
                "permissions": [
                    f"{manifest.name}.{perm}"
                    for perm in next(
                        (m.get_permissions() for m in module if m.name == info.name),
                        [],
                    )
                ],
            }
        )

    return ApiResponse(data=active)


def _nav_visible(item: dict[str, Any], granted: list[str]) -> bool:
    perm = item.get("permission")
    if not perm:
        return True
    return any(permission_matches(perm, g) for g in granted)


@router.get("/-/doctor")
async def module_doctor(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[dict[str, Any]]:
    svc = ModuleService(db)
    return ApiResponse(data=(await svc.doctor()).to_dict())


@router.get("/{name}/-/operations")
async def module_operations(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
    limit: int = 20,
) -> ApiResponse[list[dict[str, Any]]]:
    """Return the most recent operation log rows for ``name``.

    ``limit`` is clamped to ``[1, 100]``. 404 if the module is unknown.
    """
    clamped = max(1, min(limit, 100))
    svc = ModuleService(db)
    try:
        entries = await svc.operation_log(name, limit=clamped)
    except ModuleOperationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(data=[entry.to_dict() for entry in entries])


# --- Mutating endpoints --------------------------------------------------


@router.post("/{name}/install", status_code=status.HTTP_202_ACCEPTED)
async def install_module(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    __: Annotated[None, Depends(block_in_demo)],
    force: bool = False,
) -> ApiResponse[dict[str, Any]]:
    svc = ModuleService(db)
    try:
        scheduled = await svc.install(name, force=force)
    except ModuleOperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(
        data={"scheduled": scheduled, "requires_restart": bool(scheduled)},
        message="Restart required to apply.",
    )


@router.post("/{name}/uninstall", status_code=status.HTTP_202_ACCEPTED)
async def uninstall_module(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    __: Annotated[None, Depends(block_in_demo)],
    force: bool = False,
) -> ApiResponse[dict[str, Any]]:
    svc = ModuleService(db)
    try:
        await svc.uninstall(name, force=force)
    except ModuleOperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(
        data={"scheduled": [name], "requires_restart": True},
        message="Restart required to apply. A data backup will be created before removal.",
    )


@router.post("/{name}/upgrade", status_code=status.HTTP_202_ACCEPTED)
async def upgrade_module(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    __: Annotated[None, Depends(block_in_demo)],
) -> ApiResponse[dict[str, Any]]:
    svc = ModuleService(db)
    try:
        changed = await svc.upgrade(name)
    except ModuleOperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(
        data={"scheduled": [name] if changed else [], "requires_restart": changed},
        message=(
            "Restart required to apply."
            if changed
            else "Module is already at the declared version."
        ),
    )


@router.post("/-/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart_backend(
    background_tasks: BackgroundTasks,
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    __: Annotated[None, Depends(block_in_demo)],
) -> ApiResponse[dict[str, Any]]:
    """Send SIGTERM to container PID 1 so Docker respawns the process.

    The endpoint returns immediately; the actual shutdown runs in a
    background task with a small delay so the HTTP response flushes
    first. The container must have ``restart: unless-stopped`` set for
    the respawn to happen (see ``docker-compose.yml``).

    We target PID 1 rather than ``os.getpid()`` because under uvicorn's
    ``--reload`` (dev mode) the supervisor is PID 1 and the app worker
    is a child — killing only the worker leaves the supervisor idle
    without spawning a replacement. In production (no ``--reload``)
    PID 1 *is* the worker, so the same kill works identically.
    """
    background_tasks.add_task(_graceful_exit)
    return ApiResponse(
        data={"pid": os.getpid()},
        message="Restart scheduled.",
    )


async def _graceful_exit() -> None:
    await asyncio.sleep(0.5)
    logger.info("Sending SIGTERM to PID 1 (current pid=%s) for module restart", os.getpid())
    try:
        os.kill(1, signal.SIGTERM)
    except PermissionError:
        # Fallback: signal self. Works in prod where we are PID 1.
        logger.warning("No permission to signal PID 1; signalling self instead")
        os.kill(os.getpid(), signal.SIGTERM)
