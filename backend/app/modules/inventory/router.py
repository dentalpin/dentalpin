"""Inventory HTTP surface. Mounts under ``/api/v1/inventory/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    InventoryAdjust,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
)
from .service import InventoryService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[InventoryItemResponse])
async def list_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    low_stock_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[InventoryItemResponse]:
    items, total = await InventoryService.list_items(
        db, ctx.clinic_id, category, search, low_stock_only, page, page_size
    )
    return PaginatedApiResponse(
        data=[InventoryItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ApiResponse[InventoryItemResponse])
async def create_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: InventoryItemCreate,
) -> ApiResponse[InventoryItemResponse]:
    item = await InventoryService.create_item(db, ctx.clinic_id, payload, ctx.user_id)
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.patch("/{item_id}", response_model=ApiResponse[InventoryItemResponse])
async def update_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    payload: InventoryItemUpdate,
) -> ApiResponse[InventoryItemResponse]:
    item = await InventoryService.update_item(db, ctx.clinic_id, item_id, payload)
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.post("/{item_id}/adjust", response_model=ApiResponse[InventoryItemResponse])
async def adjust_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    payload: InventoryAdjust,
) -> ApiResponse[InventoryItemResponse]:
    item = await InventoryService.adjust_quantity(db, ctx.clinic_id, item_id, payload)
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.delete("/{item_id}", response_model=ApiResponse[None])
async def delete_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
) -> ApiResponse[None]:
    await InventoryService.delete_item(db, ctx.clinic_id, item_id)
    return ApiResponse(data=None)
