"""purchase_orders HTTP surface — mounted at ``/api/v1/purchase_orders/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .pdf import PurchaseOrderPDFService
from .schemas import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    PurchaseReceiptCreate,
    PurchaseReceiptResponse,
    StatusTransition,
)
from .service import PurchaseOrderService

router = APIRouter()


@router.get("", response_model=PaginatedApiResponse[PurchaseOrderResponse])
async def list_purchase_orders(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    order_status: str | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[PurchaseOrderResponse]:
    items, total = await PurchaseOrderService.list_order_responses(
        db,
        ctx.clinic_id,
        order_status=order_status,
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[PurchaseOrderResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_id}", response_model=ApiResponse[PurchaseOrderResponse])
async def get_purchase_order(
    order_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PurchaseOrderResponse]:
    response = await PurchaseOrderService.get_order_response(db, ctx.clinic_id, order_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(response))


@router.post(
    "", response_model=ApiResponse[PurchaseOrderResponse], status_code=status.HTTP_201_CREATED
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PurchaseOrderResponse]:
    order = await PurchaseOrderService.create_order(db, ctx.clinic_id, data, ctx.user_id)
    response = await PurchaseOrderService.get_order_response(db, ctx.clinic_id, order.id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(response))


@router.patch("/{order_id}", response_model=ApiResponse[PurchaseOrderResponse])
async def update_purchase_order(
    order_id: UUID,
    data: PurchaseOrderUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PurchaseOrderResponse]:
    await PurchaseOrderService.update_order(db, ctx.clinic_id, order_id, data)
    response = await PurchaseOrderService.get_order_response(db, ctx.clinic_id, order_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(response))


@router.post("/{order_id}/status", response_model=ApiResponse[PurchaseOrderResponse])
async def transition_purchase_order(
    order_id: UUID,
    data: StatusTransition,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PurchaseOrderResponse]:
    await PurchaseOrderService.transition_order(db, ctx.clinic_id, order_id, data)
    response = await PurchaseOrderService.get_order_response(db, ctx.clinic_id, order_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(response))


@router.post("/{order_id}/receive", response_model=ApiResponse[PurchaseOrderResponse])
async def receive_purchase_order(
    order_id: UUID,
    data: PurchaseReceiptCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PurchaseOrderResponse]:
    await PurchaseOrderService.receive_order(db, ctx.clinic_id, order_id, data, ctx.user_id)
    response = await PurchaseOrderService.get_order_response(db, ctx.clinic_id, order_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(response))


@router.get("/{order_id}/receipts", response_model=PaginatedApiResponse[PurchaseReceiptResponse])
async def list_purchase_receipts(
    order_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[PurchaseReceiptResponse]:
    await PurchaseOrderService.get_order(db, ctx.clinic_id, order_id)  # 404 mapping
    receipts = await PurchaseOrderService.list_receipts(db, ctx.clinic_id, order_id)
    data = [
        await PurchaseOrderService.get_receipt_response(db, ctx.clinic_id, receipt.id)
        for receipt in receipts
    ]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=len(data))


@router.get(
    "/{order_id}/receipts/{receipt_id}", response_model=ApiResponse[PurchaseReceiptResponse]
)
async def get_purchase_receipt(
    order_id: UUID,
    receipt_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PurchaseReceiptResponse]:
    await PurchaseOrderService.get_order(db, ctx.clinic_id, order_id)  # 404 mapping
    response = await PurchaseOrderService.get_receipt_response(db, ctx.clinic_id, receipt_id)
    return ApiResponse(data=PurchaseReceiptResponse.model_validate(response))


@router.get("/{order_id}/pdf")
async def download_purchase_order_pdf(
    order_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern="^(es|en)$"),
) -> Response:
    """Download a purchase order as PDF (export, no signature section)."""
    await PurchaseOrderService.get_order(db, ctx.clinic_id, order_id)  # 404 mapping
    response = await PurchaseOrderService.get_order_response(db, ctx.clinic_id, order_id)

    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)
    pdf_bytes = await PurchaseOrderPDFService.generate_pdf(response, clinic, locale)

    filename = f"purchase_order_{order_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
