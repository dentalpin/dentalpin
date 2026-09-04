"""inventory_reorder HTTP surface — mounted at ``/api/v1/inventory_reorder/``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.purchase_orders.schemas import PurchaseOrderResponse

from .schemas import ReorderOrdersCreate, ReorderSuggestionResponse
from .service import ReorderService

router = APIRouter()


@router.get("/suggestions", response_model=ApiResponse[list[ReorderSuggestionResponse]])
async def list_reorder_suggestions(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory_reorder.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[ReorderSuggestionResponse]]:
    suggestions = await ReorderService.compute_suggestions(db, ctx.clinic_id)
    return ApiResponse(data=[ReorderSuggestionResponse.model_validate(s) for s in suggestions])


@router.post(
    "/orders",
    response_model=ApiResponse[list[PurchaseOrderResponse]],
    status_code=status.HTTP_201_CREATED,
)
async def create_reorder_orders(
    data: ReorderOrdersCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory_reorder.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PurchaseOrderResponse]]:
    orders = await ReorderService.generate_orders(db, ctx.clinic_id, data.item_ids, ctx.user_id)
    return ApiResponse(data=[PurchaseOrderResponse.model_validate(o) for o in orders])
