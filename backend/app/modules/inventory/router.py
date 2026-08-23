"""Inventory HTTP surface — mounted at ``/api/v1/inventory/``.

All endpoints filter by ``clinic_id`` from the request context.
Permissions: ``inventory.{read,write,delete}``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ItemCreate,
    ItemDetailResponse,
    ItemFilters,
    ItemResponse,
    ItemUpdate,
    LowStockResponse,
    StockAdjustRequest,
)
from .service import InventoryCategoryService, InventoryItemService

router = APIRouter()


# --- Categories -----------------------------------------------------------


@router.get(
    "/categories",
    response_model=PaginatedApiResponse[CategoryResponse],
)
async def list_categories(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedApiResponse[CategoryResponse]:
    items, total = await InventoryCategoryService.list(
        db, ctx.clinic_id, include_inactive=include_inactive, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[CategoryResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/categories",
    response_model=ApiResponse[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: CategoryCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CategoryResponse]:
    category = await InventoryCategoryService.create(db, ctx.clinic_id, data.model_dump())
    await db.commit()
    return ApiResponse(data=CategoryResponse.model_validate(category))


@router.get(
    "/categories/{category_id}",
    response_model=ApiResponse[CategoryResponse],
)
async def get_category(
    category_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CategoryResponse]:
    category = await InventoryCategoryService.get(db, ctx.clinic_id, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return ApiResponse(data=CategoryResponse.model_validate(category))


@router.patch(
    "/categories/{category_id}",
    response_model=ApiResponse[CategoryResponse],
)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CategoryResponse]:
    category = await InventoryCategoryService.update(
        db, ctx.clinic_id, category_id, data.model_dump(exclude_unset=True)
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.commit()
    return ApiResponse(data=CategoryResponse.model_validate(category))


# --- Items ----------------------------------------------------------------


@router.get(
    "/",
    response_model=PaginatedApiResponse[ItemResponse],
)
async def list_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    category_id: UUID | None = None,
    low_stock: bool = False,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedApiResponse[ItemResponse]:
    filters = ItemFilters(
        status=status_filter,
        category_id=category_id,
        low_stock=low_stock,
        search=search,
    )
    items, total = await InventoryItemService.list(
        db, ctx.clinic_id, filters, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[ItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=ApiResponse[ItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    data: ItemCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ItemResponse]:
    item = await InventoryItemService.create(db, ctx.clinic_id, data.model_dump())
    await db.commit()
    return ApiResponse(data=ItemResponse.model_validate(item))


@router.get(
    "/low-stock",
    response_model=ApiResponse[list[LowStockResponse]],
)
async def low_stock_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[LowStockResponse]]:
    items = await InventoryItemService.low_stock_items(db, ctx.clinic_id)
    return ApiResponse(
        data=[
            LowStockResponse(
                item_id=i.id,
                code=i.code,
                name=i.name,
                quantity=i.quantity,
                min_quantity=i.min_quantity,
                unit=i.unit,
            )
            for i in items
        ]
    )


@router.get(
    "/stats/dashboard",
    response_model=ApiResponse[dict],
)
async def stock_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    summary = await InventoryItemService.stock_summary(db, ctx.clinic_id)
    return ApiResponse(data=summary)


@router.get(
    "/{item_id}",
    response_model=ApiResponse[ItemDetailResponse],
)
async def get_item(
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ItemDetailResponse]:
    item = await InventoryItemService.get(db, ctx.clinic_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ApiResponse(data=ItemDetailResponse.model_validate(item))


@router.patch(
    "/{item_id}",
    response_model=ApiResponse[ItemResponse],
)
async def update_item(
    item_id: UUID,
    data: ItemUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ItemResponse]:
    item = await InventoryItemService.update(
        db, ctx.clinic_id, item_id, data.model_dump(exclude_unset=True)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.commit()
    return ApiResponse(data=ItemResponse.model_validate(item))


@router.post(
    "/{item_id}/adjust-stock",
    response_model=ApiResponse[ItemResponse],
)
async def adjust_stock(
    item_id: UUID,
    data: StockAdjustRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ItemResponse]:
    item = await InventoryItemService.adjust_stock(db, ctx.clinic_id, item_id, data.delta)
    if not item:
        raise HTTPException(
            status_code=400,
            detail="Stock adjustment rejected: insufficient quantity or item not found",
        )
    await db.commit()
    return ApiResponse(data=ItemResponse.model_validate(item))


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_item(
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory.delete"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    item = await InventoryItemService.delete(db, ctx.clinic_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.commit()
    return None
