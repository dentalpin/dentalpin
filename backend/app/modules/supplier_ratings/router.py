"""supplier_ratings HTTP surface — mounted at ``/api/v1/supplier_ratings/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    SupplierRatingResponse,
    SupplierReviewCreate,
    SupplierReviewResponse,
    SupplierReviewUpdate,
)
from .service import SupplierRatingsService

router = APIRouter()


def _rating_response(item: dict) -> SupplierRatingResponse:
    return SupplierRatingResponse(
        supplier_id=item["supplier_id"],
        supplier_name=item["supplier_name"],
        metrics=item["metrics"],
        review=(SupplierReviewResponse.model_validate(item["review"]) if item["review"] else None),
    )


@router.get("", response_model=PaginatedApiResponse[SupplierRatingResponse])
async def list_supplier_ratings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[SupplierRatingResponse]:
    items, total = await SupplierRatingsService.list_ratings(db, ctx.clinic_id, page, page_size)
    return PaginatedApiResponse(
        data=[_rating_response(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.get("/{supplier_id}", response_model=ApiResponse[SupplierRatingResponse])
async def get_supplier_rating(
    supplier_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierRatingResponse]:
    item, _ = await SupplierRatingsService.get_ratings(db, ctx.clinic_id, supplier_id)
    return ApiResponse(data=_rating_response(item))


@router.post(
    "/reviews",
    response_model=ApiResponse[SupplierReviewResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier_review(
    data: SupplierReviewCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierReviewResponse]:
    review = await SupplierRatingsService.create_review(db, ctx.clinic_id, data, ctx.user_id)
    return ApiResponse(data=SupplierReviewResponse.model_validate(review))


@router.get("/reviews/{review_id}", response_model=ApiResponse[SupplierReviewResponse])
async def get_supplier_review(
    review_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierReviewResponse]:
    review, _ = await SupplierRatingsService.get_review(db, ctx.clinic_id, review_id)
    return ApiResponse(data=SupplierReviewResponse.model_validate(review))


@router.patch("/reviews/{review_id}", response_model=ApiResponse[SupplierReviewResponse])
async def update_supplier_review(
    review_id: UUID,
    data: SupplierReviewUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SupplierReviewResponse]:
    review = await SupplierRatingsService.update_review(db, ctx.clinic_id, review_id, data)
    return ApiResponse(data=SupplierReviewResponse.model_validate(review))


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier_review(
    review_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("supplier_ratings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await SupplierRatingsService.delete_review(db, ctx.clinic_id, review_id)
