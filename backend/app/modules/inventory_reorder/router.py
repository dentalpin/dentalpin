"""Reorder suggestions + PO generation. Mounts under
``/api/v1/inventory_reorder/*``."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import GeneratePOsRequest, GeneratePOsResponse, ReorderSuggestion
from .service import ReorderService

router = APIRouter()


@router.get("/suggestions", response_model=ApiResponse[list[ReorderSuggestion]])
async def get_suggestions(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory_reorder.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[ReorderSuggestion]]:
    suggestions = await ReorderService.get_suggestions(db, ctx.clinic_id)
    return ApiResponse(data=[ReorderSuggestion(**s) for s in suggestions])


@router.post("/generate-pos", response_model=ApiResponse[GeneratePOsResponse])
async def generate_pos(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("inventory_reorder.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: GeneratePOsRequest,
) -> ApiResponse[GeneratePOsResponse]:
    po_ids = await ReorderService.generate_purchase_orders(
        db,
        ctx.clinic_id,
        [s.model_dump() for s in payload.selections],
        ctx.user_id,
    )
    return ApiResponse(data=GeneratePOsResponse(purchase_order_ids=po_ids))
