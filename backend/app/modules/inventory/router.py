"""Inventory HTTP surface. Mounts under ``/api/v1/inventory/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    StockAdjustPayload,
    StockMovementResponse,
    StockValuationResponse,
)
from .service import InventoryService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[InventoryItemResponse])
async def list_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None),
    low_stock: bool = Query(default=False),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[InventoryItemResponse]:
    items, total = await InventoryService.list_items(
        db,
        ctx.clinic_id,
        category=category,
        low_stock_only=low_stock,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[InventoryItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/valuation", response_model=ApiResponse[StockValuationResponse])
async def stock_valuation(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[StockValuationResponse]:
    """Total on-hand value over active items with a known unit cost (#226)."""
    return ApiResponse(data=await InventoryService.stock_valuation(db, ctx.clinic_id))


@router.get("/{item_id}", response_model=ApiResponse[InventoryItemResponse])
async def get_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
) -> ApiResponse[InventoryItemResponse]:
    item = await InventoryService.get_item(db, ctx.clinic_id, item_id)
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.post(
    "/", response_model=ApiResponse[InventoryItemResponse], status_code=status.HTTP_201_CREATED
)
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
    item = await InventoryService.update_item(
        db, ctx.clinic_id, item_id, payload, created_by=ctx.user_id
    )
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.post("/{item_id}/adjust", response_model=ApiResponse[InventoryItemResponse])
async def adjust_stock(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    payload: StockAdjustPayload,
) -> ApiResponse[InventoryItemResponse]:
    """Relative stock change (+ restock / - consumption), applied atomically.

    Rejects with 409 when the delta would drive stock below zero. Every
    adjustment is recorded in the movements ledger (#226).
    """
    item = await InventoryService.adjust_stock(
        db,
        ctx.clinic_id,
        item_id,
        payload.delta,
        reason=payload.reason,
        note=payload.note,
        created_by=ctx.user_id,
    )
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.get("/{item_id}/movements", response_model=PaginatedApiResponse[StockMovementResponse])
async def list_movements(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    reason: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedApiResponse[StockMovementResponse]:
    """The audit trail for one item — every quantity change ever applied."""
    # 404 when the item doesn't exist / belongs to another clinic.
    await InventoryService.get_item(db, ctx.clinic_id, item_id)
    rows, total = await InventoryService.list_movements(
        db,
        ctx.clinic_id,
        inventory_item_id=item_id,
        reason=reason,
        page=page,
        page_size=page_size,
    )
    # Each row is a dict with 'movement' (ORM) and 'created_by_name' (str | None).
    data = []
    for row in rows:
        resp = StockMovementResponse.model_validate(row["movement"])
        resp.created_by_name = row["created_by_name"]
        data.append(resp)
    return PaginatedApiResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
) -> None:
    await InventoryService.delete_item(db, ctx.clinic_id, item_id)
