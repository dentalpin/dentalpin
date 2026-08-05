"""Supplier-item pricing links. Mounts under ``/api/v1/supplier_items/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .models import SupplierItem
from .schemas import SupplierItemCreate, SupplierItemResponse, SupplierItemUpdate
from .service import SupplierItemService

router = APIRouter()


def _to_response(row: tuple[SupplierItem, str, str, int | None]) -> SupplierItemResponse:
    link, supplier_name, item_name, lead_time_days = row
    return SupplierItemResponse(
        id=link.id,
        clinic_id=link.clinic_id,
        supplier_contact_id=link.supplier_contact_id,
        supplier_name=supplier_name,
        inventory_item_id=link.inventory_item_id,
        item_name=item_name,
        supplier_sku=link.supplier_sku,
        unit_price=link.unit_price,
        is_preferred_supplier=link.is_preferred_supplier,
        lead_time_days=lead_time_days,
        notes=link.notes,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.get("/", response_model=PaginatedApiResponse[SupplierItemResponse])
async def list_links(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    supplier_contact_id: UUID | None = Query(default=None),
    inventory_item_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> PaginatedApiResponse[SupplierItemResponse]:
    rows, total = await SupplierItemService.list_links(
        db, ctx.clinic_id, supplier_contact_id, inventory_item_id, page, page_size
    )
    return PaginatedApiResponse(
        data=[_to_response(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("/", response_model=ApiResponse[SupplierItemResponse])
async def create_link(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: SupplierItemCreate,
) -> ApiResponse[SupplierItemResponse]:
    row = await SupplierItemService.create(db, ctx.clinic_id, payload)
    return ApiResponse(data=_to_response(row))


@router.patch("/{link_id}", response_model=ApiResponse[SupplierItemResponse])
async def update_link(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    link_id: UUID,
    payload: SupplierItemUpdate,
) -> ApiResponse[SupplierItemResponse]:
    row = await SupplierItemService.update(db, ctx.clinic_id, link_id, payload)
    return ApiResponse(data=_to_response(row))


@router.delete("/{link_id}", response_model=ApiResponse[None])
async def delete_link(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    link_id: UUID,
) -> ApiResponse[None]:
    await SupplierItemService.delete(db, ctx.clinic_id, link_id)
    return ApiResponse(data=None)
