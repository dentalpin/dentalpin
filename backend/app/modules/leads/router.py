"""Staff HTTP surface for leads.

Mounted at /api/v1/leads/. Collection routes are declared as "/" (the
contacts / staff_tasks convention) and the app runs with
redirect_slashes=False — the frontend must call /api/v1/leads/ *with*
the trailing slash. /api/v1/leads 404s.

Settings routes are declared before the /{lead_id} routes on purpose:
FastAPI matches in declaration order, so "/settings" would otherwise be
parsed as a lead id.

Cross-module permission rule: a route that discloses or writes another
module's data carries that module's permission too. POST / needs
patients.read (it returns the matched patient's name), POST
/{id}/convert needs patients.write (it creates a patient).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.patients.schemas import PatientBrief

from .models import Lead
from .schemas import (
    INTAKE_PATH,
    IntakeKeyRotated,
    IntakeKeyUpdate,
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadIntakeKeyStatus,
    LeadResponse,
    LeadSettingsResponse,
    LeadSettingsUpdate,
    LeadSubmitResponse,
    LeadUpdate,
)
from .service import (
    LeadIntakeKeyService,
    LeadIntakeService,
    LeadService,
    LeadSettingsService,
)

router = APIRouter()


async def _ensure_lead(db: AsyncSession, clinic_id: UUID, lead_id: UUID) -> Lead:
    """404 (not 403) on an unknown *or* other-clinic id — no existence leak."""
    lead = await LeadService.get_lead(db, clinic_id, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


async def _settings_response(db: AsyncSession, clinic_id: UUID) -> LeadSettingsResponse:
    """One GET feeds the whole settings page (cap + gauge + key status)."""
    settings = await LeadSettingsService.get_or_create(db, clinic_id)
    key = await LeadIntakeKeyService.get_key(db, clinic_id)
    return LeadSettingsResponse(
        daily_cap=settings.daily_cap,
        day_count=settings.day_count,
        day_count_date=settings.day_count_date,
        intake_url=INTAKE_PATH,
        key=LeadIntakeKeyStatus(
            configured=key is not None,
            key_prefix=key.key_prefix if key else None,
            is_active=bool(key.is_active) if key else False,
            last_used_at=key.last_used_at if key else None,
        ),
    )


# --- Leads ----------------------------------------------------------------


@router.get("/", response_model=PaginatedApiResponse[LeadResponse])
async def list_leads(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[str | None, Query()] = None,
) -> PaginatedApiResponse[LeadResponse]:
    """No status filter means all four statuses — discarded is not hidden."""
    items, total = await LeadService.list_leads(
        db,
        ctx.clinic_id,
        status=status_filter,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    return PaginatedApiResponse(
        data=[LeadResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/", response_model=ApiResponse[LeadSubmitResponse], status_code=status.HTTP_201_CREATED
)
async def submit_lead(
    data: LeadCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.write"))],
    __: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadSubmitResponse]:
    """Manual creation by the front desk — same routing as the public form.

    patients.read is required because the recall_queued branch returns
    recalled_patient, a matched patient's name. The outcome union means
    the front desk is never told "saved" when the row went to Recalls.
    """
    result = await LeadIntakeService.route(
        db, ctx.clinic_id, data.model_dump(), recommended_by=ctx.user_id
    )

    if result.outcome == "lead_created" and result.lead is not None:
        return ApiResponse(
            data=LeadSubmitResponse(
                outcome="lead_created",
                lead=LeadResponse.model_validate(result.lead),
            )
        )

    # A shared family phone can match two or three patients (each gets a
    # recall); the staff contract reports the highest-ranked match.
    first = result.recalled_patients[0] if result.recalled_patients else None
    return ApiResponse(
        data=LeadSubmitResponse(
            outcome="recall_queued",
            recalled_patient=PatientBrief.model_validate(first) if first else None,
        )
    )


# --- Settings (D13) — declared before /{lead_id} ---------------------------


@router.get("/settings", response_model=ApiResponse[LeadSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadSettingsResponse]:
    """Lazy-creates the settings row; never mints an intake key."""
    return ApiResponse(data=await _settings_response(db, ctx.clinic_id))


@router.patch("/settings", response_model=ApiResponse[LeadSettingsResponse])
async def update_settings(
    data: LeadSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadSettingsResponse]:
    """Only daily_cap (0 = unlimited). Never resets the day counter."""
    await LeadSettingsService.update(db, ctx.clinic_id, data.model_dump(exclude_unset=True))
    return ApiResponse(data=await _settings_response(db, ctx.clinic_id))


@router.post(
    "/settings/intake-key/rotate",
    response_model=ApiResponse[IntakeKeyRotated],
)
async def rotate_intake_key(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IntakeKeyRotated]:
    """Creates or rotates the key; the plaintext is returned exactly once."""
    key, plaintext = await LeadIntakeKeyService.rotate(db, ctx.clinic_id)
    return ApiResponse(data=IntakeKeyRotated(key=plaintext, key_prefix=key.key_prefix))


@router.patch(
    "/settings/intake-key",
    response_model=ApiResponse[LeadIntakeKeyStatus],
)
async def set_intake_key_active(
    data: IntakeKeyUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadIntakeKeyStatus]:
    """The kill switch: an inactive key answers 401 like an unknown one."""
    key = await LeadIntakeKeyService.set_active(db, ctx.clinic_id, data.is_active)
    return ApiResponse(
        data=LeadIntakeKeyStatus(
            configured=True,
            key_prefix=key.key_prefix,
            is_active=key.is_active,
            last_used_at=key.last_used_at,
        )
    )


# --- Lead detail -----------------------------------------------------------


@router.get("/{lead_id}", response_model=ApiResponse[LeadResponse])
async def get_lead(
    lead_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadResponse]:
    lead = await _ensure_lead(db, ctx.clinic_id, lead_id)
    return ApiResponse(data=LeadResponse.model_validate(lead))


@router.patch("/{lead_id}", response_model=ApiResponse[LeadResponse])
async def update_lead(
    lead_id: UUID,
    data: LeadUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadResponse]:
    """All-optional body + exclude_unset: an empty PATCH changes nothing."""
    lead = await _ensure_lead(db, ctx.clinic_id, lead_id)
    lead = await LeadService.update_lead(db, lead, data.model_dump(exclude_unset=True))
    return ApiResponse(data=LeadResponse.model_validate(lead))


@router.post("/{lead_id}/convert", response_model=ApiResponse[LeadConvertResponse])
async def convert_lead(
    lead_id: UUID,
    data: LeadConvertRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.write"))],
    __: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadConvertResponse]:
    """Create the patient and link the lead, atomically.

    Two permission dependencies are intentional: leads.write owns the
    action, patients.write guarantees the caller may create a patient.
    Dropping one lets a leads.write-only role create patient records.
    """
    lead = await _ensure_lead(db, ctx.clinic_id, lead_id)
    lead, patient = await LeadService.convert(db, ctx.clinic_id, lead, data.model_dump())
    return ApiResponse(
        data=LeadConvertResponse(
            lead=LeadResponse.model_validate(lead),
            patient=PatientBrief.model_validate(patient),
        )
    )
