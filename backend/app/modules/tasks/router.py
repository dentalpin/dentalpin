"""Tasks (handoff board) HTTP surface. Mounts under ``/api/v1/tasks/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import AssignableUser, TaskCreate, TaskResponse, TaskUpdate
from .service import TaskService

router = APIRouter()


@router.get("/assignable-users", response_model=ApiResponse[list[AssignableUser]])
async def list_assignable_users(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("tasks.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AssignableUser]]:
    users = await TaskService.list_assignable_users(db, ctx.clinic_id)
    return ApiResponse(data=[AssignableUser.model_validate(u) for u in users])


@router.get("/", response_model=PaginatedApiResponse[TaskResponse])
async def list_tasks(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("tasks.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    task_status: str | None = Query(default=None),
    assigned_to: UUID | None = Query(default=None),
    priority: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[TaskResponse]:
    tasks, total = await TaskService.list_task_responses(
        db, ctx.clinic_id, task_status, assigned_to, priority, page, page_size
    )
    return PaginatedApiResponse(
        data=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ApiResponse[TaskResponse])
async def create_task(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("tasks.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: TaskCreate,
) -> ApiResponse[TaskResponse]:
    task = await TaskService.create_task(db, ctx.clinic_id, payload, ctx.user_id)
    enriched = await TaskService.get_task_response(db, ctx.clinic_id, task.id)
    return ApiResponse(data=TaskResponse.model_validate(enriched))


@router.patch("/{task_id}", response_model=ApiResponse[TaskResponse])
async def update_task(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("tasks.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    task_id: UUID,
    payload: TaskUpdate,
) -> ApiResponse[TaskResponse]:
    task = await TaskService.update_task(db, ctx.clinic_id, task_id, payload)
    enriched = await TaskService.get_task_response(db, ctx.clinic_id, task.id)
    return ApiResponse(data=TaskResponse.model_validate(enriched))


@router.delete("/{task_id}", response_model=ApiResponse[None])
async def delete_task(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("tasks.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    task_id: UUID,
) -> ApiResponse[None]:
    await TaskService.delete_task(db, ctx.clinic_id, task_id)
    return ApiResponse(data=None)
