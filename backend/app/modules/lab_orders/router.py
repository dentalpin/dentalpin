"""Lab orders HTTP surface. Mounts under ``/api/v1/lab-orders/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import LabOrderCreate, LabOrderResponse, LabOrderUpdate
from .service import LabOrderService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[LabOrderResponse])
async def list_lab_orders(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("lab_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: UUID | None = Query(default=None),
    lab_contact_id: UUID | None = Query(default=None),
    order_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[LabOrderResponse]:
    orders, total = await LabOrderService.list_order_responses(
        db, ctx.clinic_id, patient_id, lab_contact_id, order_status, page, page_size
    )
    return PaginatedApiResponse(
        data=[LabOrderResponse.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_id}", response_model=ApiResponse[LabOrderResponse])
async def get_lab_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("lab_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    order_id: UUID,
) -> ApiResponse[LabOrderResponse]:
    order = await LabOrderService.get_order_response(db, ctx.clinic_id, order_id)
    return ApiResponse(data=LabOrderResponse.model_validate(order))


@router.post("/", response_model=ApiResponse[LabOrderResponse])
async def create_lab_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("lab_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: LabOrderCreate,
) -> ApiResponse[LabOrderResponse]:
    order = await LabOrderService.create_order(db, ctx.clinic_id, payload, ctx.user_id)
    enriched = await LabOrderService.get_order_response(db, ctx.clinic_id, order.id)
    return ApiResponse(data=LabOrderResponse.model_validate(enriched))


@router.patch("/{order_id}", response_model=ApiResponse[LabOrderResponse])
async def update_lab_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("lab_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    order_id: UUID,
    payload: LabOrderUpdate,
) -> ApiResponse[LabOrderResponse]:
    order = await LabOrderService.update_order(db, ctx.clinic_id, order_id, payload)
    enriched = await LabOrderService.get_order_response(db, ctx.clinic_id, order.id)
    return ApiResponse(data=LabOrderResponse.model_validate(enriched))


@router.delete("/{order_id}", response_model=ApiResponse[None])
async def delete_lab_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("lab_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    order_id: UUID,
) -> ApiResponse[None]:
    await LabOrderService.delete_order(db, ctx.clinic_id, order_id)
    return ApiResponse(data=None)
