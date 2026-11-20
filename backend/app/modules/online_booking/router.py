"""Public booking endpoints and authenticated reception actions."""

import hashlib
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.models import User
from app.core.auth.router import limiter
from app.database import get_db
from app.modules.agenda.locks import lock_clinic
from app.modules.agenda.service import AppointmentService, CabinetService
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService
from app.modules.schedules.services.clinic_hours import ClinicHoursService

from .models import BookingRequest, BookingSettings
from .outbox import enqueue
from .rate_limit import consume_rate
from .schemas import AcceptInput, ConfirmInput, RejectInput, RequestInput, SettingsInput
from .service import live_hold, occupied, reserve, slots

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]
CTX = Annotated[ClinicContext, Depends(get_clinic_context)]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def public_settings(db: AsyncSession, clinic_id: UUID) -> BookingSettings:
    config = await db.get(BookingSettings, clinic_id)
    if config is None or not config.enabled or not config.public_url or not config.professional_id:
        raise HTTPException(404, "Booking unavailable")
    return config


@router.get("/settings")
async def get_settings(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.settings"))]
):
    config = await db.get(BookingSettings, ctx.clinic_id)
    if config is None:
        return {"data": SettingsInput().model_dump(mode="json")}
    return {
        "data": SettingsInput.model_validate(config, from_attributes=True).model_dump(mode="json")
    }


@router.get("/public/{clinic_id}/config")
@limiter.limit("60/minute")
async def public_config(request: Request, clinic_id: UUID, db: DB):
    await consume_rate("availability-ip", request.client.host if request.client else "unknown", 240)
    config = await public_settings(db, clinic_id)
    return {
        "data": {
            "slot_minutes": config.slot_minutes,
            "timezone": await ClinicHoursService.get_clinic_timezone(db, clinic_id),
            "reasons": ["first_visit", "checkup"],
        }
    }


@router.put("/settings")
async def update_settings(
    data: SettingsInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.settings"))],
):
    if data.enabled and (not data.public_url or not data.professional_id):
        raise HTTPException(422, "A public URL and professional are required")
    if data.professional_id and not await AppointmentService.validate_professional_access(
        db, ctx.clinic_id, data.professional_id
    ):
        raise HTTPException(422, "Invalid professional")
    await lock_clinic(db, ctx.clinic_id)
    config = await db.get(BookingSettings, ctx.clinic_id)
    if config is None:
        config = BookingSettings(clinic_id=ctx.clinic_id)
        db.add(config)
    for key, value in data.model_dump().items():
        setattr(config, key, value)
    await db.flush()
    return {"data": data.model_dump(mode="json")}


@router.get("/public/{clinic_id}/availability")
@limiter.limit("60/minute")
async def availability(request: Request, clinic_id: UUID, day: date, db: DB):
    await consume_rate("availability-ip", request.client.host if request.client else "unknown", 240)
    config = await public_settings(db, clinic_id)
    starts = await slots(db, clinic_id, config, day, datetime.now(UTC))
    return {
        "data": {
            "starts": [start.isoformat() for start in starts],
            "slot_minutes": config.slot_minutes,
        }
    }


@router.post("/public/{clinic_id}/requests", status_code=201)
@limiter.limit("10/hour")
async def create_request(request: Request, clinic_id: UUID, data: RequestInput, db: DB):
    await consume_rate("request-ip", request.client.host if request.client else "unknown", 10)
    if data.website:
        raise HTTPException(400, "Unable to process request")
    await consume_rate("request-contact", f"{clinic_id}:{str(data.contact_email).lower()}", 3)
    config = await public_settings(db, clinic_id)
    # The clinic lock also makes the contact quota check atomic for this clinic.
    await lock_clinic(db, clinic_id)
    now = datetime.now(UTC)
    email = str(data.contact_email).strip().lower()
    recent = await db.scalar(
        select(func.count())
        .select_from(BookingRequest)
        .where(
            BookingRequest.clinic_id == clinic_id,
            BookingRequest.contact_email == email,
            BookingRequest.created_at > now - timedelta(hours=1),
        )
    )
    if recent >= 3:
        raise HTTPException(429, "Too many requests")
    token = secrets.token_urlsafe(32)
    start = data.start_time.astimezone(UTC)
    item = BookingRequest(
        clinic_id=clinic_id,
        start_time=start,
        end_time=start + timedelta(minutes=config.slot_minutes),
        status="pending_confirmation",
        contact_name=data.contact_name,
        contact_email=email,
        contact_phone=data.contact_phone,
        reason=data.reason,
        confirmation_deadline=now + timedelta(minutes=10),
        token_hash=digest(token),
    )
    try:
        await reserve(db, clinic_id, config, item, now)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    # The client-side confirmation page must consume the fragment explicitly.
    link = f"{config.public_url}#token={token}"
    enqueue(
        db,
        clinic_id,
        item.id,
        "confirmation",
        {
            "email": email,
            "subject": "Confirm your booking request",
            "text": f"Confirm your request within 10 minutes: {link}",
            "link": link,
        },
    )
    return {"data": {"message": "Your confirmation email has been queued."}}


@router.post("/public/{clinic_id}/confirm")
@limiter.limit("10/minute")
async def confirm(request: Request, clinic_id: UUID, data: ConfirmInput, db: DB):
    await consume_rate("confirm-ip", request.client.host if request.client else "unknown", 120)
    await public_settings(db, clinic_id)
    await lock_clinic(db, clinic_id)
    item = await db.scalar(
        select(BookingRequest)
        .where(
            BookingRequest.clinic_id == clinic_id, BookingRequest.token_hash == digest(data.token)
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if (
        item is None
        or item.status != "pending_confirmation"
        or item.confirmation_deadline <= now
        or item.start_time <= now
    ):
        raise HTTPException(410, "Confirmation link expired or invalid")
    if await occupied(db, clinic_id, item.start_time, item.end_time, now, exclude=item.id):
        raise HTTPException(409, "Time slot is occupied; choose another time")
    item.status = "confirmed"
    item.token_hash = None
    await db.flush()
    return {"data": {"status": "confirmed"}}


@router.get("/requests/count")
async def count_requests(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.read"))]
):
    total = await db.scalar(
        select(func.count())
        .select_from(BookingRequest)
        .where(
            BookingRequest.clinic_id == ctx.clinic_id,
            BookingRequest.status == "confirmed",
            BookingRequest.start_time > datetime.now(UTC),
        )
    )
    return {"data": total or 0}


@router.get("/requests")
async def list_requests(
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.read"))],
    page: int = Query(default=1, ge=1, le=100000),
):
    page_size = 50
    rows = (
        await db.scalars(
            select(BookingRequest)
            .where(
                BookingRequest.clinic_id == ctx.clinic_id,
                live_hold(datetime.now(UTC)),
            )
            .order_by(BookingRequest.start_time, BookingRequest.id)
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        )
    ).all()
    config = await db.get(BookingSettings, ctx.clinic_id)
    return {
        "data": [
            {
                "id": str(row.id),
                "status": row.status,
                "start_time": row.start_time.isoformat(),
                "end_time": row.end_time.isoformat(),
                "contact_name": row.contact_name,
                "contact_email": row.contact_email,
                "contact_phone": row.contact_phone,
                "reason": row.reason,
                "default_duration_minutes": (
                    getattr(config, f"{row.reason}_minutes", None)
                    or (
                        config.slot_minutes
                        if config
                        else int((row.end_time - row.start_time).total_seconds() / 60)
                    )
                ),
            }
            for row in rows[:page_size]
        ],
        "page": page,
        "has_more": len(rows) > page_size,
    }


@router.get("/requests/{request_id}/patient-suggestions")
async def patient_suggestions(
    request_id: UUID,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.read"))],
    __: Annotated[None, Depends(require_permission("patients.read"))],
):
    row = await db.scalar(
        select(BookingRequest).where(
            BookingRequest.id == request_id, BookingRequest.clinic_id == ctx.clinic_id
        )
    )
    if row is None:
        raise HTTPException(404, "Request not found")
    matches = []
    if row.contact_email:
        matches.append(func.lower(Patient.email) == row.contact_email.strip().lower())
    phone = re.sub(r"\D", "", row.contact_phone or "")
    if phone:
        matches.append(func.regexp_replace(Patient.phone, "[^0-9]", "", "g") == phone)
    if not matches:
        return {"data": []}
    patients = (
        await db.scalars(
            select(Patient)
            .where(Patient.clinic_id == ctx.clinic_id, Patient.status != "archived", or_(*matches))
            .order_by(Patient.first_name, Patient.last_name, Patient.id)
            .limit(10)
        )
    ).all()
    return {
        "data": [
            {
                "id": str(p.id),
                "first_name": p.first_name,
                "last_name": p.last_name,
                "phone": p.phone,
                "email": p.email,
                "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            }
            for p in patients
        ]
    }


@router.post("/requests/{request_id}/accept")
async def accept(
    request_id: UUID,
    data: AcceptInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.write"))],
):
    from app.core.auth.rbac import has_permission_for

    for permission in ("agenda.appointments.write", "patients.write"):
        if not await has_permission_for(db, ctx.clinic_id, ctx.role, permission):
            raise HTTPException(403, f"Permission denied: {permission}")
    await lock_clinic(db, ctx.clinic_id)
    row = await db.scalar(
        select(BookingRequest)
        .where(BookingRequest.id == request_id, BookingRequest.clinic_id == ctx.clinic_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if row is None:
        raise HTTPException(404, "Request not found")
    if row.status != "confirmed" or row.start_time <= now:
        raise HTTPException(409, "Request cannot be accepted")
    if not await AppointmentService.validate_professional_access(
        db, ctx.clinic_id, data.professional_id
    ) or not await db.scalar(
        select(User.id).where(User.id == data.professional_id, User.is_active.is_(True))
    ):
        raise HTTPException(422, "Invalid professional")
    if data.cabinet_id:
        cabinet = await CabinetService.get_cabinet(db, ctx.clinic_id, data.cabinet_id)
        if not cabinet or not cabinet.is_active:
            raise HTTPException(422, "Invalid cabinet")
    end_time = row.start_time + timedelta(minutes=data.duration_minutes)
    # Clinic-wide scope blocks any active appointment or live hold across all
    # professionals and cabinets, including the selected resources.
    if await occupied(db, ctx.clinic_id, row.start_time, end_time, now, exclude=row.id):
        raise HTTPException(409, "Time slot is occupied; choose another time")
    if data.patient_id:
        if not await AppointmentService.validate_patient_access(db, ctx.clinic_id, data.patient_id):
            raise HTTPException(404, "Patient not found")
        patient_id = data.patient_id
    else:
        if not data.first_name or data.last_name is None:
            raise HTTPException(422, "Enter a first name and confirm the surname field")
        patient = await PatientService.create_patient(
            db,
            ctx.clinic_id,
            {
                "first_name": data.first_name,
                "last_name": data.last_name,
                "email": (str(data.email) if data.email else None)
                if "email" in data.model_fields_set
                else row.contact_email,
                "phone": data.phone if "phone" in data.model_fields_set else row.contact_phone,
            },
        )
        patient_id = patient.id
    try:
        appt = await AppointmentService.create_appointment(
            db,
            ctx.clinic_id,
            {
                "patient_id": patient_id,
                "professional_id": data.professional_id,
                "cabinet_id": data.cabinet_id,
                "start_time": row.start_time,
                "end_time": end_time,
            },
            created_by=ctx.user_id,
        )
    except IntegrityError as exc:
        raise HTTPException(409, "Time slot is occupied; choose another time") from exc
    row.status = "accepted"
    row.end_time = end_time
    row.decided_at = now
    row.patient_id = patient_id
    row.appointment_id = appt.id
    await db.flush()
    return {"data": {"status": "accepted", "appointment_id": str(appt.id)}}


@router.post("/requests/{request_id}/reject")
async def reject(
    request_id: UUID,
    data: RejectInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.write"))],
):
    await lock_clinic(db, ctx.clinic_id)
    row = await db.scalar(
        select(BookingRequest)
        .where(BookingRequest.id == request_id, BookingRequest.clinic_id == ctx.clinic_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "Request not found")
    now = datetime.now(UTC)
    if (
        row.status not in ("pending_confirmation", "confirmed")
        or row.status == "pending_confirmation"
        and row.confirmation_deadline <= now
        or row.status == "confirmed"
        and row.start_time <= now
    ):
        raise HTTPException(409, "Request expired or already decided")
    if row.contact_email:
        enqueue(
            db,
            ctx.clinic_id,
            row.id,
            "rejection",
            {
                "email": row.contact_email,
                "subject": "Update on your booking request",
                "text": data.message,
            },
        )
    row.status = "rejected"
    row.decided_at = now
    row.token_hash = None
    row.rejection_message = data.message
    await db.flush()
    return {"data": {"status": "rejected"}}
