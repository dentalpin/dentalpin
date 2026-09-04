"""supplier_items HTTP surface — mounted at ``/api/v1/supplier_items/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import SupplierItemCreate, SupplierItemResponse, SupplierItemUpdate
from .service import SupplierItemService

router = APIRouter()


@router.get("", response_model=PaginatedApiResponse[SupplierItemResponse])
async def list_supplier_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: UUID | None = Query(default=None),
    inventory_item_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[SupplierItemResponse]:
    items, total = await SupplierItemService.list_links(
        db,
        ctx.clinic_id,
        supplier_id=supplier_id,
        inventory_item_id=inventory_item_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[SupplierItemResponse.from_link(link, sname, iname) for link, sname, iname in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{link_id}", response_model=ApiResponse[SupplierItemResponse])
async def get_supplier_item(
    link_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierItemResponse]:
    result = await SupplierItemService.get_link(db, ctx.clinic_id, link_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier item link not found"
        )
    link, sname, iname = result
    return ApiResponse(data=SupplierItemResponse.from_link(link, sname, iname))


@router.post(
    "", response_model=ApiResponse[SupplierItemResponse], status_code=status.HTTP_201_CREATED
)
async def create_supplier_item(
    data: SupplierItemCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierItemResponse]:
    link, sname, iname = await SupplierItemService.create_link(db, ctx.clinic_id, data)
    return ApiResponse(data=SupplierItemResponse.from_link(link, sname, iname))


@router.patch("/{link_id}", response_model=ApiResponse[SupplierItemResponse])
async def update_supplier_item(
    link_id: UUID,
    data: SupplierItemUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierItemResponse]:
    result = await SupplierItemService.get_link(db, ctx.clinic_id, link_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier item link not found"
        )
    link, sname, iname = result

    link = await SupplierItemService.update_link(db, link, data)
    return ApiResponse(data=SupplierItemResponse.from_link(link, sname, iname))


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier_item(
    link_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_items.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete (L7): marks the link inactive, keeping the row for history."""
    result = await SupplierItemService.get_link(db, ctx.clinic_id, link_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier item link not found"
        )
    link, _, _ = result
    await SupplierItemService.deactivate_link(db, link)
