"""Contacts HTTP surface. Mounts under ``/api/v1/contacts/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import ContactCreate, ContactResponse, ContactUpdate
from .service import ContactService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[ContactResponse])
async def list_contacts(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_type: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ContactResponse]:
    contacts, total = await ContactService.list_contacts(
        db, ctx.clinic_id, contact_type, search, include_inactive, page, page_size
    )
    return PaginatedApiResponse(
        data=[ContactResponse.model_validate(c) for c in contacts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{contact_id}", response_model=ApiResponse[ContactResponse])
async def get_contact(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: UUID,
) -> ApiResponse[ContactResponse]:
    contact = await ContactService.get_contact(db, ctx.clinic_id, contact_id)
    return ApiResponse(data=ContactResponse.model_validate(contact))


@router.post("/", response_model=ApiResponse[ContactResponse])
async def create_contact(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ContactCreate,
) -> ApiResponse[ContactResponse]:
    contact = await ContactService.create_contact(db, ctx.clinic_id, payload)
    return ApiResponse(data=ContactResponse.model_validate(contact))


@router.patch("/{contact_id}", response_model=ApiResponse[ContactResponse])
async def update_contact(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: UUID,
    payload: ContactUpdate,
) -> ApiResponse[ContactResponse]:
    contact = await ContactService.update_contact(db, ctx.clinic_id, contact_id, payload)
    return ApiResponse(data=ContactResponse.model_validate(contact))


@router.delete("/{contact_id}", response_model=ApiResponse[None])
async def delete_contact(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: UUID,
) -> ApiResponse[None]:
    await ContactService.delete_contact(db, ctx.clinic_id, contact_id)
    return ApiResponse(data=None)
