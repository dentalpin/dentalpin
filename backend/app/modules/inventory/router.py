"""Inventory HTTP surface. Mounts under ``/api/v1/inventory/*``."""

import csv
import io
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    InventoryAdjust,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementReason,
    InventoryMovementResponse,
    InventoryUsageSummary,
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
    page_size: int = Query(default=20, ge=1, le=1000),
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
    """Quick signed-delta adjust. Kept for backward compatibility —
    internally recorded as an 'adjustment' movement (see /movements)."""
    item = await InventoryService.adjust_quantity(db, ctx.clinic_id, item_id, payload, ctx.user_id)
    return ApiResponse(data=InventoryItemResponse.model_validate(item))


@router.get("/{item_id}/movements", response_model=PaginatedApiResponse[InventoryMovementResponse])
async def list_movements(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    reason: InventoryMovementReason | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
) -> PaginatedApiResponse[InventoryMovementResponse]:
    movements, total = await InventoryService.list_movements(
        db, ctx.clinic_id, item_id, reason, date_from, date_to, page, page_size
    )
    return PaginatedApiResponse(
        data=[InventoryMovementResponse.model_validate(m) for m in movements],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{item_id}/movements", response_model=ApiResponse[InventoryMovementResponse])
async def create_movement(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    payload: InventoryMovementCreate,
) -> ApiResponse[InventoryMovementResponse]:
    _item, movement = await InventoryService.record_movement(
        db, ctx.clinic_id, item_id, payload, ctx.user_id
    )
    return ApiResponse(data=InventoryMovementResponse.model_validate(movement))


@router.get("/{item_id}/movements/export")
async def export_movements(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
    reason: InventoryMovementReason | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> StreamingResponse:
    """CSV export of the movement audit trail (capped at 5000 rows)."""
    movements = await InventoryService.export_movements(
        db, ctx.clinic_id, item_id, reason, date_from, date_to
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "movement_date",
            "reason",
            "quantity_delta",
            "quantity_after",
            "unit_cost",
            "reference",
            "notes",
        ]
    )
    for m in movements:
        writer.writerow(
            [
                m.movement_date.isoformat(),
                m.reason,
                m.quantity_delta,
                m.quantity_after,
                m.unit_cost if m.unit_cost is not None else "",
                m.reference or "",
                (m.notes or "").replace("\n", " "),
            ]
        )
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=inventory-movements-{item_id}.csv"
        },
    )


@router.get("/{item_id}/usage", response_model=ApiResponse[InventoryUsageSummary])
async def get_usage(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
) -> ApiResponse[InventoryUsageSummary]:
    summary = await InventoryService.usage_summary(db, ctx.clinic_id, item_id)
    return ApiResponse(data=InventoryUsageSummary(**summary))


@router.delete("/{item_id}", response_model=ApiResponse[None])
async def delete_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: UUID,
) -> ApiResponse[None]:
    await InventoryService.delete_item(db, ctx.clinic_id, item_id)
    return ApiResponse(data=None)
