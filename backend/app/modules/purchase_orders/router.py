"""Purchase orders HTTP surface. Mounts under ``/api/v1/purchase_orders/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.contacts.models import Contact

from .pdf import PurchaseOrderPDFService
from .receiving_service import ReceivingService
from .schemas import (
    PurchaseOrderCancel,
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    PurchaseOrderItemUpdate,
    PurchaseOrderListItem,
    PurchaseOrderReceiptCreate,
    PurchaseOrderReceiptResponse,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from .service import PurchaseOrderService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[PurchaseOrderListItem])
async def list_orders(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    supplier_contact_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> PaginatedApiResponse[PurchaseOrderListItem]:
    rows, total = await PurchaseOrderService.list_orders(
        db, ctx.clinic_id, status_filter, supplier_contact_id, search, page, page_size
    )
    data = [
        PurchaseOrderListItem(
            id=po.id,
            po_number=po.po_number,
            supplier_contact_id=po.supplier_contact_id,
            supplier_name=supplier_name,
            status=po.status,
            order_date=po.order_date,
            expected_delivery_date=po.expected_delivery_date,
            total=po.total,
        )
        for po, supplier_name in rows
    ]
    return PaginatedApiResponse(data=data, total=total, page=page, page_size=page_size)


@router.get("/{po_id}", response_model=ApiResponse[PurchaseOrderResponse])
async def get_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.get(db, ctx.clinic_id, po_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.post("/", response_model=ApiResponse[PurchaseOrderResponse])
async def create_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: PurchaseOrderCreate,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.create(db, ctx.clinic_id, payload, ctx.user_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.patch("/{po_id}", response_model=ApiResponse[PurchaseOrderResponse])
async def update_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    payload: PurchaseOrderUpdate,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.update(db, ctx.clinic_id, po_id, payload)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.delete("/{po_id}", response_model=ApiResponse[None])
async def delete_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
) -> ApiResponse[None]:
    await PurchaseOrderService.delete(db, ctx.clinic_id, po_id)
    return ApiResponse(data=None)


# ---------------------------------------------------------------- line items

@router.post("/{po_id}/items", response_model=ApiResponse[PurchaseOrderResponse])
async def add_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    payload: PurchaseOrderItemCreate,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.add_item(db, ctx.clinic_id, po_id, payload)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.patch("/{po_id}/items/{item_id}", response_model=ApiResponse[PurchaseOrderResponse])
async def update_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    item_id: UUID,
    payload: PurchaseOrderItemUpdate,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.update_item(db, ctx.clinic_id, po_id, item_id, payload)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.delete("/{po_id}/items/{item_id}", response_model=ApiResponse[PurchaseOrderResponse])
async def remove_item(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    item_id: UUID,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.remove_item(db, ctx.clinic_id, po_id, item_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


# ---------------------------------------------------------------- lifecycle

@router.post("/{po_id}/send", response_model=ApiResponse[PurchaseOrderResponse])
async def send_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    send_email: bool = Query(
        default=True,
        description="If false, marks the PO sent without emailing the supplier (e.g. sent by phone).",
    ),
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.send(db, ctx.clinic_id, po_id, ctx.user_id, send_email)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.post("/{po_id}/confirm", response_model=ApiResponse[PurchaseOrderResponse])
async def confirm_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.confirm(db, ctx.clinic_id, po_id, ctx.user_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


@router.post("/{po_id}/cancel", response_model=ApiResponse[PurchaseOrderResponse])
async def cancel_order(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    payload: PurchaseOrderCancel,
) -> ApiResponse[PurchaseOrderResponse]:
    po = await PurchaseOrderService.cancel(db, ctx.clinic_id, po_id, ctx.user_id, payload.reason)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))


# ---------------------------------------------------------------- PDF

@router.get("/{po_id}/pdf")
async def get_pdf(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    locale: str = Query(default="es"),
) -> Response:
    po = await PurchaseOrderService.get(db, ctx.clinic_id, po_id)
    supplier = await db.get(Contact, po.supplier_contact_id)

    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)

    pdf_bytes = await PurchaseOrderPDFService.generate_pdf(po, supplier, clinic, locale)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{po.po_number}.pdf"'},
    )


# ---------------------------------------------------------------- receiving

@router.get("/{po_id}/receipts", response_model=ApiResponse[list[PurchaseOrderReceiptResponse]])
async def list_receipts(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
) -> ApiResponse[list[PurchaseOrderReceiptResponse]]:
    receipts = await ReceivingService.list_receipts(db, ctx.clinic_id, po_id)
    return ApiResponse(data=[PurchaseOrderReceiptResponse.model_validate(r) for r in receipts])


@router.post("/{po_id}/receipts", response_model=ApiResponse[PurchaseOrderResponse])
async def record_receipt(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("purchase_orders.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_id: UUID,
    payload: PurchaseOrderReceiptCreate,
) -> ApiResponse[PurchaseOrderResponse]:
    po, _receipt = await ReceivingService.record_receipt(db, ctx.clinic_id, po_id, payload, ctx.user_id)
    return ApiResponse(data=PurchaseOrderResponse.model_validate(po))
