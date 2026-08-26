"""Medication catalog HTTP surface. Mounts under
``/api/v1/medication_catalog/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    MedicationCatalogCreate,
    MedicationCatalogResponse,
    MedicationCatalogUpdate,
    MedicationSeedSummary,
)
from .service import MedicationCatalogService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[MedicationCatalogResponse])
async def list_medications(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medication_catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None, max_length=150),
    form: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedApiResponse[MedicationCatalogResponse]:
    items, total = await MedicationCatalogService.list_items(
        db, ctx.clinic_id, q=q, form=form, is_active=is_active, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[MedicationCatalogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{item_id}", response_model=ApiResponse[MedicationCatalogResponse])
async def get_medication(
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medication_catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationCatalogResponse]:
    item = await MedicationCatalogService.get_item(db, ctx.clinic_id, item_id)
    return ApiResponse(data=MedicationCatalogResponse.model_validate(item))


@router.post(
    "/",
    response_model=ApiResponse[MedicationCatalogResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_medication(
    payload: MedicationCatalogCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medication_catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationCatalogResponse]:
    item = await MedicationCatalogService.create_item(db, ctx.clinic_id, payload)
    return ApiResponse(data=MedicationCatalogResponse.model_validate(item))


@router.patch("/{item_id}", response_model=ApiResponse[MedicationCatalogResponse])
async def update_medication(
    item_id: UUID,
    payload: MedicationCatalogUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medication_catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationCatalogResponse]:
    item = await MedicationCatalogService.update_item(db, ctx.clinic_id, item_id, payload)
    return ApiResponse(data=MedicationCatalogResponse.model_validate(item))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medication_catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await MedicationCatalogService.delete_item(db, ctx.clinic_id, item_id)


@router.post("/seed", response_model=ApiResponse[MedicationSeedSummary])
async def seed_medication_catalog(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medication_catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationSeedSummary]:
    """Re-run the idempotent 56-item dental seeder for this clinic."""
    from .seed import seed_medications

    summary = await seed_medications(db, ctx.clinic_id)
    await db.commit()
    return ApiResponse(data=MedicationSeedSummary(**summary))
