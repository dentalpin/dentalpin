"""treatment_consumables HTTP surface. Mounts under
``/api/v1/treatment_consumables/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    ConsumableLinkCreate,
    ConsumableLinkDetailed,
    ConsumableLinkUpdate,
    LinkOptionsResponse,
)
from .service import TreatmentConsumablesService, treatment_display_name

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[ConsumableLinkDetailed])
async def list_links(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treatment_consumables.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    catalog_item_id: UUID | None = Query(default=None),
    inventory_item_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedApiResponse[ConsumableLinkDetailed]:
    links, total = await TreatmentConsumablesService.list_links(
        db,
        ctx.clinic_id,
        catalog_item_id=catalog_item_id,
        inventory_item_id=inventory_item_id,
        page=page,
        page_size=page_size,
    )
    detailed = await TreatmentConsumablesService.detailed_links(db, ctx.clinic_id, links)
    return PaginatedApiResponse(
        data=[ConsumableLinkDetailed(**d) for d in detailed],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/link-options", response_model=ApiResponse[LinkOptionsResponse])
async def link_options(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treatment_consumables.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None, max_length=150),
) -> ApiResponse[LinkOptionsResponse]:
    """Search-based picker data from both dependency modules, gated on
    this module's own read permission."""
    treatments, items = await TreatmentConsumablesService.link_options(db, ctx.clinic_id, q=q)
    return ApiResponse(
        data=LinkOptionsResponse(
            treatments=[
                {
                    "id": t.id,
                    "name": treatment_display_name(t),
                    "internal_code": t.internal_code,
                }
                for t in treatments
            ],
            items=[{"id": i.id, "name": i.name, "unit": i.unit} for i in items],
        )
    )


@router.post(
    "/",
    response_model=ApiResponse[ConsumableLinkDetailed],
    status_code=status.HTTP_201_CREATED,
)
async def create_link(
    payload: ConsumableLinkCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treatment_consumables.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ConsumableLinkDetailed]:
    link = await TreatmentConsumablesService.create_link(
        db,
        ctx.clinic_id,
        payload.catalog_item_id,
        payload.inventory_item_id,
        payload.quantity,
        note=payload.note,
    )
    detailed = await TreatmentConsumablesService.detailed_links(db, ctx.clinic_id, [link])
    return ApiResponse(data=ConsumableLinkDetailed(**detailed[0]))


@router.patch("/{link_id}", response_model=ApiResponse[ConsumableLinkDetailed])
async def update_link(
    link_id: UUID,
    payload: ConsumableLinkUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treatment_consumables.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ConsumableLinkDetailed]:
    link = await TreatmentConsumablesService.update_quantity(
        db, ctx.clinic_id, link_id, payload.quantity, note=payload.note
    )
    detailed = await TreatmentConsumablesService.detailed_links(db, ctx.clinic_id, [link])
    return ApiResponse(data=ConsumableLinkDetailed(**detailed[0]))


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treatment_consumables.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await TreatmentConsumablesService.delete_link(db, ctx.clinic_id, link_id)
