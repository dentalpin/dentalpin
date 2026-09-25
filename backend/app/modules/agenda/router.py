"""Agenda HTTP surface: appointments + cabinets.

Mounts at ``/api/v1/agenda/*``. Appointments use the
``agenda.appointments.*`` namespace; cabinets still gate on
``admin.clinic.write`` until Etapa B.2 chunk 3 normalizes cabinets
into their own table + permission namespace.
"""

from datetime import date as date_type
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .checkin import (
    CheckinTokenError,
    mint_checkin_token,
    render_checkin_qr,
    verify_checkin_token,
)
from .kanban_service import KanbanDayService
from .models import Appointment
from .schemas import (
    AppointmentCabinetAssignment,
    AppointmentCabinetEventResponse,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusEventResponse,
    AppointmentStatusTransition,
    AppointmentTreatmentNoteUpdate,
    AppointmentTreatmentResponse,
    AppointmentUpdate,
    CabinetCreate,
    CabinetResponse,
    CabinetUpdate,
    CheckinResultResponse,
    CheckinTokenResponse,
    KanbanDaySnapshot,
)
from .service import (
    AlreadyInStateError,
    AppointmentService,
    CabinetRequiredError,
    CabinetService,
    InvalidTransitionError,
)
from .tz import safe_zone

router = APIRouter()


def _localize(response: AppointmentResponse, ctx: ClinicContext) -> AppointmentResponse:
    """Serialize start/end in the clinic timezone (issue #161).

    Wall-clock consumers (the calendar grid slices the ISO string) and
    instant consumers (``new Date()`` on the dashboard) then both render
    the hour the receptionist picked. Audit timestamps stay UTC.
    """
    tz = safe_zone(ctx.clinic.timezone)
    response.start_time = response.start_time.astimezone(tz)
    response.end_time = response.end_time.astimezone(tz)
    return response


# --- Appointments -------------------------------------------------------


@router.get("/appointments", response_model=PaginatedApiResponse[AppointmentResponse])
async def list_appointments(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    cabinet: str | None = None,
    professional_id: UUID | None = None,
    patient_id: UUID | None = None,
    appointment_status: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> PaginatedApiResponse[AppointmentResponse]:
    """List appointments with filters.

    ``order`` sorts by ``start_time`` — ``desc`` lets "most recent
    first" consumers (e.g. the patient last-visit card) fetch one page
    of one instead of paging to the tail.
    """
    appointments, total = await AppointmentService.list_appointments(
        db,
        ctx.clinic_id,
        start_date,
        end_date,
        cabinet,
        professional_id,
        appointment_status,
        page,
        page_size,
        patient_id=patient_id,
        order=order,
    )
    return PaginatedApiResponse(
        data=[_localize(AppointmentResponse.model_validate(a), ctx) for a in appointments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/appointments",
    response_model=ApiResponse[AppointmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    data: AppointmentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AppointmentResponse]:
    """Create a new appointment."""
    if data.patient_id:
        if not await AppointmentService.validate_patient_access(db, ctx.clinic_id, data.patient_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

    if not await AppointmentService.validate_professional_access(
        db, ctx.clinic_id, data.professional_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid professional: must be a dentist or hygienist in this clinic",
        )

    try:
        appointment = await AppointmentService.create_appointment(
            db,
            ctx.clinic_id,
            data.model_dump(exclude_unset=True),
            created_by=ctx.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot is already occupied",
        ) from e

    return ApiResponse(data=_localize(AppointmentResponse.model_validate(appointment), ctx))


@router.get("/appointments/{appointment_id}.ics")
async def export_appointment_ics(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Export one appointment as an RFC 5545 ``.ics`` file (#129).

    Lets a patient or professional drop the appointment into Google
    Calendar / Apple Calendar / Outlook. Timestamps go out in UTC.
    Registered before the plain ``/{appointment_id}`` route: starlette
    matches routes in order and ``{appointment_id}`` (``[^/]+``) would
    swallow the ``.ics`` suffix into the UUID and 422.
    """
    from .ics import build_appointment_ics

    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return Response(
        content=build_appointment_ics(appointment, ctx.clinic),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="appointment-{appointment.id}.ics"'},
    )


@router.get("/appointments/{appointment_id}", response_model=ApiResponse[AppointmentResponse])
async def get_appointment(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AppointmentResponse]:
    """Get an appointment by ID, including the status audit trail."""
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    events = await AppointmentService.list_status_events(db, ctx.clinic_id, appointment.id)
    response = _localize(AppointmentResponse.model_validate(appointment), ctx)
    response.history = [AppointmentStatusEventResponse.model_validate(e) for e in events]
    return ApiResponse(data=response)


@router.put("/appointments/{appointment_id}", response_model=ApiResponse[AppointmentResponse])
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AppointmentResponse]:
    """Update an appointment."""
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if data.patient_id:
        if not await AppointmentService.validate_patient_access(db, ctx.clinic_id, data.patient_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

    if data.professional_id:
        if not await AppointmentService.validate_professional_access(
            db, ctx.clinic_id, data.professional_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid professional: must be a dentist or hygienist in this clinic",
            )

    try:
        appointment = await AppointmentService.update_appointment(
            db,
            appointment,
            data.model_dump(exclude_unset=True),
            changed_by=ctx.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot is already occupied",
        ) from e

    return ApiResponse(data=_localize(AppointmentResponse.model_validate(appointment), ctx))


@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Cancel an appointment."""
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    try:
        await AppointmentService.cancel_appointment(db, appointment, changed_by=ctx.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/appointments/{appointment_id}/transitions",
    response_model=ApiResponse[AppointmentResponse],
)
async def transition_appointment(
    appointment_id: UUID,
    data: AppointmentStatusTransition,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AppointmentResponse]:
    """Advance (or cancel) an appointment's status.

    Returns the full appointment with its ``history`` populated so the
    frontend can update the detail view in one round-trip.
    """
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    try:
        await AppointmentService.transition(
            db, appointment, data.to_status, changed_by=ctx.user_id, note=data.note
        )
    except AlreadyInStateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except CabinetRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    events = await AppointmentService.list_status_events(db, ctx.clinic_id, appointment.id)
    response = _localize(AppointmentResponse.model_validate(appointment), ctx)
    response.history = [AppointmentStatusEventResponse.model_validate(e) for e in events]
    return ApiResponse(data=response)


@router.get(
    "/appointments/{appointment_id}/transitions",
    response_model=ApiResponse[list[AppointmentStatusEventResponse]],
)
async def list_appointment_transitions(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AppointmentStatusEventResponse]]:
    """Return the full status audit trail for an appointment (asc)."""
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    events = await AppointmentService.list_status_events(db, ctx.clinic_id, appointment.id)
    return ApiResponse(data=[AppointmentStatusEventResponse.model_validate(e) for e in events])


@router.patch(
    "/appointments/{appointment_id}/cabinet",
    response_model=ApiResponse[AppointmentResponse],
)
async def assign_appointment_cabinet(
    appointment_id: UUID,
    data: AppointmentCabinetAssignment,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AppointmentResponse]:
    """Assign, reassign, or (with ``cabinet_id=null``) unassign a cabinet.

    Returns the updated appointment with its cabinet history populated so
    the frontend can update the detail view in one round-trip.
    """
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    try:
        await AppointmentService.assign_cabinet(
            db,
            appointment,
            data.cabinet_id,
            changed_by=ctx.user_id,
            note=data.note,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot is already occupied in that cabinet",
        ) from e

    events = await AppointmentService.list_cabinet_events(db, ctx.clinic_id, appointment.id)
    response = _localize(AppointmentResponse.model_validate(appointment), ctx)
    response.cabinet_history = [AppointmentCabinetEventResponse.model_validate(e) for e in events]
    return ApiResponse(data=response)


@router.get(
    "/appointments/{appointment_id}/cabinet-history",
    response_model=ApiResponse[list[AppointmentCabinetEventResponse]],
)
async def list_appointment_cabinet_history(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AppointmentCabinetEventResponse]]:
    """Return the cabinet assignment audit trail (asc)."""
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    events = await AppointmentService.list_cabinet_events(db, ctx.clinic_id, appointment.id)
    return ApiResponse(data=[AppointmentCabinetEventResponse.model_validate(e) for e in events])


# --- Kanban day snapshot (issue #51) -----------------------------------


@router.get(
    "/kanban/day",
    response_model=ApiResponse[KanbanDaySnapshot],
)
async def get_kanban_day(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    target: date_type | None = Query(
        default=None,
        alias="date",
        description="Day to snapshot (defaults to today in the clinic timezone)",
    ),
) -> ApiResponse[KanbanDaySnapshot]:
    """Return the professionals strip state for the kanban board."""
    target_date = target or datetime.now(safe_zone(ctx.clinic.timezone)).date()
    data = await KanbanDayService.snapshot(db, ctx.clinic_id, target_date)
    return ApiResponse(data=KanbanDaySnapshot(**data))


# --- Cabinets (real table) ----------------------------------------------


@router.get("/cabinets", response_model=ApiResponse[list[CabinetResponse]])
async def list_cabinets(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.cabinets.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[CabinetResponse]]:
    """List cabinets in the current clinic."""
    cabinets = await CabinetService.list_cabinets(db, ctx.clinic_id)
    return ApiResponse(data=[CabinetResponse.model_validate(c) for c in cabinets])


@router.post(
    "/cabinets",
    response_model=ApiResponse[CabinetResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_cabinet(
    data: CabinetCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.cabinets.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CabinetResponse]:
    """Create a new cabinet in the clinic."""
    existing = await CabinetService.get_by_name(db, ctx.clinic_id, data.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cabinet name already exists",
        )

    cabinet = await CabinetService.create_cabinet(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    await db.refresh(cabinet)
    return ApiResponse(data=CabinetResponse.model_validate(cabinet))


@router.put("/cabinets/{cabinet_id}", response_model=ApiResponse[CabinetResponse])
async def update_cabinet(
    cabinet_id: UUID,
    data: CabinetUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.cabinets.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CabinetResponse]:
    """Update a cabinet."""
    cabinet = await CabinetService.get_cabinet(db, ctx.clinic_id, cabinet_id)
    if cabinet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cabinet not found",
        )

    if data.name and data.name != cabinet.name:
        clash = await CabinetService.get_by_name(db, ctx.clinic_id, data.name)
        if clash is not None and clash.id != cabinet.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cabinet name already exists",
            )

    cabinet = await CabinetService.update_cabinet(db, cabinet, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(cabinet)
    return ApiResponse(data=CabinetResponse.model_validate(cabinet))


@router.delete("/cabinets/{cabinet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cabinet(
    cabinet_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.cabinets.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a cabinet. Blocks when any non-cancelled appointment still uses it."""
    cabinet = await CabinetService.get_cabinet(db, ctx.clinic_id, cabinet_id)
    if cabinet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cabinet not found",
        )

    from sqlalchemy import func as sql_func

    in_use = (
        await db.execute(
            select(sql_func.count())
            .select_from(Appointment)
            .where(
                Appointment.cabinet_id == cabinet.id,
                Appointment.status != "cancelled",
            )
        )
    ).scalar() or 0
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cabinet has {in_use} active appointments",
        )

    await CabinetService.delete_cabinet(db, cabinet)
    await db.commit()


# --- Visit-level clinical note ------------------------------------------


@router.patch(
    "/appointment-treatments/{appointment_treatment_id}",
    response_model=ApiResponse[AppointmentTreatmentResponse],
)
async def update_appointment_treatment_note(
    appointment_treatment_id: UUID,
    data: AppointmentTreatmentNoteUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AppointmentTreatmentResponse]:
    """Update visit-level clinical note + completion flag on an AppointmentTreatment.

    Permission lives under ``clinical_notes.notes`` because conceptually this
    is the visit-level anchor of the four-level clinical-notes model even
    though the row is owned by the agenda module (issue #60).
    """
    row = await AppointmentService.update_appointment_treatment_note(
        db,
        ctx.clinic_id,
        appointment_treatment_id,
        ctx.user_id,
        notes=data.notes,
        completed_in_appointment=data.completed_in_appointment,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Appointment treatment not found")
    return ApiResponse(data=AppointmentTreatmentResponse.model_validate(row))


# --- QR check-in ---------------------------------------------------------
# Signed short-lived tokens let patients check themselves in by scanning
# a QR code — no account, no login. Minting/QR render stay behind
# appointments.write; only the single-purpose consume endpoint is public
# (rate-limited, minimal-PII response).


def _checkin_base_url() -> str:
    """Public origin check-in links and QR codes are built from.

    Single source: the first configured ``ALLOWED_ORIGINS`` entry, so a
    copied link and its QR can never point at different hosts. 422 when
    unset or not an http(s) origin.
    """
    origins = settings.allowed_origins_list
    if not origins:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set ALLOWED_ORIGINS to render check-in QR codes",
        )
    parsed = urlparse(origins[0])
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ALLOWED_ORIGINS must hold http(s) origins",
        )
    return f"{parsed.scheme}://{parsed.netloc}"


@router.post(
    "/appointments/{appointment_id}/check-in-token",
    response_model=ApiResponse[CheckinTokenResponse],
)
async def mint_appointment_checkin_token(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CheckinTokenResponse]:
    """Mint a 15-minute QR check-in token for an appointment.

    Returns the token plus the patient-facing URL, built server-side
    with the same origin logic as the QR — the frontend builds no
    check-in URLs at all, so link and QR cannot diverge.
    """
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    token, expires_at = mint_checkin_token(appointment.id, ctx.clinic_id)
    url = f"{_checkin_base_url()}/p/check-in/{token}"
    return ApiResponse(data=CheckinTokenResponse(token=token, expires_at=expires_at, url=url))


@router.get("/appointments/{appointment_id}/check-in-qr")
async def appointment_checkin_qr(
    appointment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Render the check-in QR as PNG.

    The URL is built server-side from the first configured
    ``ALLOWED_ORIGINS`` entry with the token as a path segment (never a
    query string — proxies and Referer headers must not see it). The
    mint endpoint returns the identical URL, so QR and copied link
    always match.
    """
    appointment = await AppointmentService.get_appointment(db, ctx.clinic_id, appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    token, _ = mint_checkin_token(appointment.id, ctx.clinic_id)
    png = render_checkin_qr(f"{_checkin_base_url()}/p/check-in/{token}")
    return Response(content=png, media_type="image/png")


@router.post(
    "/public/check-in/{token}",
    response_model=ApiResponse[CheckinResultResponse],
)
@limiter.limit("20/minute")
@limiter.limit(
    "5/15minute",
    key_func=lambda request: str(request.path_params.get("token")),
)
async def public_appointment_checkin(
    token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CheckinResultResponse]:
    """Consume a QR check-in token (unauthenticated, rate-limited).

    The token rides the path (never a query string) so proxies and
    Referer headers cannot pick it up. Per-IP and per-token limits apply.
    Transitions scheduled/confirmed → checked_in through the canonical
    status machine so events fire. Re-scanning an already checked-in
    appointment returns 200 with the current status (never an error) —
    the token stays replayable for its full fifteen minutes, which is
    defensible for an idempotent ``checked_in`` write and stated here
    rather than left implicit; wrong-state tokens answer 422, bad/expired
    tokens 401, unknown appointments 404 (no oracle beyond what the
    token already encodes).
    """
    try:
        appointment_id, clinic_id = verify_checkin_token(token)
    except CheckinTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    try:
        appointment = await AppointmentService.public_checkin(db, appointment_id, clinic_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        ) from None
    except (InvalidTransitionError, CabinetRequiredError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    await db.commit()
    return ApiResponse(
        data=CheckinResultResponse(appointment_id=appointment.id, status=appointment.status)
    )
