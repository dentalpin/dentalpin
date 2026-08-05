"""Treatment-consumables HTTP surface. Mounts under
``/api/v1/treatment_consumables/*``.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    TreatmentConsumableCreate,
    TreatmentConsumableRead,
    TreatmentConsumableUpdate,
)
from .service import (
    DuplicateLinkError,
    InventoryItemNotFoundError,
    TreatmentNotFoundError,
    create_link,
    delete_link,
    get_link,
    list_links,
    update_link,
)

router = APIRouter()

ReadDep = Annotated[None, Depends(require_permission("treatment_consumables.read"))]
WriteDep = Annotated[None, Depends(require_permission("treatment_consumables.write"))]


@router.get("/", response_model=PaginatedApiResponse[TreatmentConsumableRead])
async def list_treatment_consumables(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: ReadDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    treatment_id: uuid.UUID | None = Query(default=None),
    inventory_item_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
) -> PaginatedApiResponse[TreatmentConsumableRead]:
    items, total = await list_links(
        db,
        clinic_id=ctx.clinic_id,
        treatment_id=treatment_id,
        inventory_item_id=inventory_item_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[TreatmentConsumableRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=ApiResponse[TreatmentConsumableRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_treatment_consumable(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: WriteDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: TreatmentConsumableCreate,
) -> ApiResponse[TreatmentConsumableRead]:
    try:
        link = await create_link(
            db,
            clinic_id=ctx.clinic_id,
            treatment_id=payload.treatment_id,
            inventory_item_id=payload.inventory_item_id,
            quantity_needed=payload.quantity_needed,
        )
    except TreatmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Treatment not found: {exc}") from exc
    except InventoryItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Inventory item not found: {exc}") from exc
    except DuplicateLinkError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"This treatment is already linked to this inventory item: {exc}",
        ) from exc
    return ApiResponse(data=TreatmentConsumableRead.model_validate(link))


@router.get("/{link_id}", response_model=ApiResponse[TreatmentConsumableRead])
async def get_treatment_consumable(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: ReadDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    link_id: uuid.UUID,
) -> ApiResponse[TreatmentConsumableRead]:
    link = await get_link(db, clinic_id=ctx.clinic_id, link_id=link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Not found")
    return ApiResponse(data=TreatmentConsumableRead.model_validate(link))


@router.patch("/{link_id}", response_model=ApiResponse[TreatmentConsumableRead])
async def update_treatment_consumable(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: WriteDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    link_id: uuid.UUID,
    payload: TreatmentConsumableUpdate,
) -> ApiResponse[TreatmentConsumableRead]:
    link = await update_link(
        db,
        clinic_id=ctx.clinic_id,
        link_id=link_id,
        quantity_needed=payload.quantity_needed,
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Not found")
    return ApiResponse(data=TreatmentConsumableRead.model_validate(link))


@router.delete("/{link_id}", response_model=ApiResponse[None])
async def delete_treatment_consumable(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: WriteDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    link_id: uuid.UUID,
) -> ApiResponse[None]:
    deleted = await delete_link(db, clinic_id=ctx.clinic_id, link_id=link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return ApiResponse(data=None)
