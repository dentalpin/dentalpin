"""Suppliers HTTP surface. Mounts under ``/api/v1/suppliers/*``.

Permission checks intentionally reuse ``contacts.read`` / ``contacts.write``
rather than declaring separate ``suppliers.*`` permissions — a supplier
IS a contact (Phase 13 §5), so gating access identically avoids a user
who can edit contacts hitting a 403 on the supplier-specific fields.
If you'd rather have independent permissions, swap the two
``require_permission(...)`` strings below and add
``get_permissions() -> ["read", "write"]`` to `__init__.py`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.contacts.models import Contact

from .models import SupplierProfile
from .schemas import SupplierProfileResponse, SupplierProfileUpsert, SupplierResponse
from .service import SupplierService

router = APIRouter()


def _to_response(contact: Contact, profile: SupplierProfile | None) -> SupplierResponse:
    return SupplierResponse(
        contact_id=contact.id,
        name=contact.name,
        phone=contact.phone,
        email=contact.email,
        address=contact.address,
        notes=contact.notes,
        is_active=contact.is_active,
        website=profile.website if profile else None,
        payment_terms=profile.payment_terms if profile else None,
        lead_time_days=profile.lead_time_days if profile else None,
        is_preferred=profile.is_preferred if profile else False,
    )


@router.get("/", response_model=PaginatedApiResponse[SupplierResponse])
async def list_suppliers(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    is_preferred: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
) -> PaginatedApiResponse[SupplierResponse]:
    pairs, total = await SupplierService.list_suppliers(
        db, ctx.clinic_id, search, is_preferred, page, page_size
    )
    return PaginatedApiResponse(
        data=[_to_response(c, p) for c, p in pairs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{contact_id}", response_model=ApiResponse[SupplierResponse])
async def get_supplier(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: UUID,
) -> ApiResponse[SupplierResponse]:
    contact, profile = await SupplierService.get_supplier(db, ctx.clinic_id, contact_id)
    return ApiResponse(data=_to_response(contact, profile))


@router.put("/{contact_id}", response_model=ApiResponse[SupplierProfileResponse])
async def upsert_profile(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: UUID,
    payload: SupplierProfileUpsert,
) -> ApiResponse[SupplierProfileResponse]:
    profile = await SupplierService.upsert_profile(db, ctx.clinic_id, contact_id, payload)
    return ApiResponse(data=SupplierProfileResponse.model_validate(profile))


@router.delete("/{contact_id}", response_model=ApiResponse[None])
async def delete_profile(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("contacts.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    contact_id: UUID,
) -> ApiResponse[None]:
    await SupplierService.delete_profile(db, ctx.clinic_id, contact_id)
    return ApiResponse(data=None)
