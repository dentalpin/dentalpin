"""Supplier performance dashboard + manual ratings. Mounts under
``/api/v1/supplier_ratings/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import SupplierPerformanceDashboard, SupplierRatingCreate, SupplierRatingResponse
from .service import SupplierRatingService

router = APIRouter()


@router.get("/{supplier_contact_id}", response_model=ApiResponse[SupplierPerformanceDashboard])
async def get_dashboard(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    supplier_contact_id: UUID,
) -> ApiResponse[SupplierPerformanceDashboard]:
    data = await SupplierRatingService.get_dashboard(db, ctx.clinic_id, supplier_contact_id)
    return ApiResponse(data=SupplierPerformanceDashboard(**data))


@router.post("/{supplier_contact_id}", response_model=ApiResponse[SupplierRatingResponse])
async def add_rating(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    supplier_contact_id: UUID,
    payload: SupplierRatingCreate,
) -> ApiResponse[SupplierRatingResponse]:
    rating = await SupplierRatingService.add_rating(
        db, ctx.clinic_id, supplier_contact_id, payload, ctx.user_id
    )
    return ApiResponse(data=SupplierRatingResponse.model_validate(rating))
