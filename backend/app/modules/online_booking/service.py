"""Availability and transactional lifecycle for clinic booking.

Availability is that of the one professional configured in the settings:
the ``schedules`` module supplies their hours, and only their active
appointments and live holds block a slot. Other professionals' appointments
never do. On acceptance reception may pick another professional or a
cabinet; the overlap check then runs for the chosen resources.

Every write takes the shared ``agenda:clinic:`` lock and rechecks under it.
The agenda only takes that lock; the hard overlap check lives here (#905).
"""

import hashlib
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.auth.rbac import has_permission_for
from app.modules.agenda.locks import lock_clinic
from app.modules.agenda.models import Appointment
from app.modules.agenda.service import AppointmentService, CabinetService
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.service import appointment_when_context
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService
from app.modules.schedules.services.availability import AvailabilityService
from app.modules.schedules.services.clinic_hours import ClinicHoursService

from .exceptions import (
    BookingConflictError,
    BookingForbiddenError,
    BookingGoneError,
    BookingNotFoundError,
    BookingRateLimitedError,
    BookingUnavailableError,
    BookingValidationError,
)
from .models import BookingRequest, BookingSettings
from .schemas import AcceptInput, RejectInput, RequestInput, SettingsInput

ACTIVE = ("scheduled", "confirmed", "checked_in", "in_treatment")
CONFIRMATION_MINUTES = 10
PAGE_SIZE = 50
SLOT_TAKEN = "Time slot is no longer available"
SLOT_OCCUPIED = "Time slot is occupied; choose another time"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def live_hold(now: datetime):
    return or_(
        and_(
            BookingRequest.status == "pending_confirmation",
            BookingRequest.confirmation_deadline > now,
        ),
        and_(BookingRequest.status == "confirmed", BookingRequest.start_time > now),
    )


async def occupied(
    db: AsyncSession,
    clinic_id: UUID,
    start: datetime,
    end: datetime,
    now: datetime,
    *,
    professional_id: UUID,
    cabinet_id: UUID | None = None,
    exclude: UUID | None = None,
) -> bool:
    """Whether the professional (or the chosen cabinet) is busy in the interval.

    Active appointments block when they use the same professional or the same
    cabinet; live holds belong to one professional and block only theirs.
    """
    resources = [Appointment.professional_id == professional_id]
    if cabinet_id is not None:
        resources.append(Appointment.cabinet_id == cabinet_id)
    appointment = await db.scalar(
        select(Appointment.id)
        .where(
            Appointment.clinic_id == clinic_id,
            Appointment.status.in_(ACTIVE),
            Appointment.start_time < end,
            Appointment.end_time > start,
            or_(*resources),
        )
        .limit(1)
    )
    if appointment is not None:
        return True
    query = select(BookingRequest.id).where(
        BookingRequest.clinic_id == clinic_id,
        BookingRequest.professional_id == professional_id,
        live_hold(now),
        BookingRequest.start_time < end,
        BookingRequest.end_time > start,
    )
    if exclude is not None:
        query = query.where(BookingRequest.id != exclude)
    return await db.scalar(query.limit(1)) is not None


async def bookable_professional(db: AsyncSession, clinic_id: UUID, professional_id: UUID) -> bool:
    """Whether the user is active and still a professional member of the clinic.

    Settings validate the professional only when saved; a later deactivation or
    removal from the clinic must stop the public page from booking them (#1100).
    """
    return await AppointmentService.validate_professional_access(
        db, clinic_id, professional_id
    ) and bool(
        await db.scalar(select(User.id).where(User.id == professional_id, User.is_active.is_(True)))
    )


async def slots(
    db: AsyncSession, clinic_id: UUID, config: BookingSettings, day: date, now: datetime
) -> list[datetime]:
    professional_id = config.professional_id
    if professional_id is None:
        return []
    tz_name, ranges = await AvailabilityService.resolve(
        db, clinic_id, day, day, professional_id=professional_id
    )
    zone = ZoneInfo(tz_name)
    today = now.astimezone(zone).date()
    if day < today or day > today + timedelta(days=config.window_days):
        return []
    duration = timedelta(minutes=config.slot_minutes)
    windows = [window for window in ranges if window.state == "open"]
    if not windows:
        return []
    start = min(window.start for window in windows)
    end = max(window.end for window in windows)
    appointments = (
        await db.execute(
            select(Appointment.start_time, Appointment.end_time).where(
                Appointment.clinic_id == clinic_id,
                Appointment.professional_id == professional_id,
                Appointment.status.in_(ACTIVE),
                Appointment.start_time < end,
                Appointment.end_time > start,
            )
        )
    ).all()
    holds = (
        await db.execute(
            select(BookingRequest.start_time, BookingRequest.end_time).where(
                BookingRequest.clinic_id == clinic_id,
                BookingRequest.professional_id == professional_id,
                live_hold(now),
                BookingRequest.start_time < end,
                BookingRequest.end_time > start,
            )
        )
    ).all()
    busy = [*appointments, *holds]
    result = []
    for window in windows:
        cursor = window.start.astimezone(UTC)
        stop = window.end.astimezone(UTC)
        while cursor + duration <= stop:
            if cursor >= now + timedelta(minutes=config.min_notice_minutes) and not any(
                begin < cursor + duration and finish > cursor for begin, finish in busy
            ):
                result.append(cursor)
            cursor += duration
    return result


async def reserve(
    db: AsyncSession, clinic_id: UUID, config: BookingSettings, item: BookingRequest, now: datetime
) -> None:
    await lock_clinic(db, clinic_id)
    now = datetime.now(UTC)
    # Reload settings after waiting; an administrator may have disabled booking
    # or changed the professional.
    await db.refresh(config)
    if (
        not config.enabled
        or config.professional_id is None
        or not await bookable_professional(db, clinic_id, config.professional_id)
    ):
        raise BookingConflictError("Booking is disabled")
    item.professional_id = config.professional_id
    item.end_time = item.start_time + timedelta(minutes=config.slot_minutes)
    zone_name, _ = await AvailabilityService.resolve(
        db,
        clinic_id,
        item.start_time.date(),
        item.start_time.date(),
        professional_id=config.professional_id,
    )
    day = item.start_time.astimezone(ZoneInfo(zone_name)).date()
    allowed = await slots(db, clinic_id, config, day, now)
    if item.start_time.astimezone(UTC) not in allowed:
        raise BookingConflictError(SLOT_TAKEN)
    db.add(item)
    await db.flush()


async def _locked_request(db: AsyncSession, clinic_id: UUID, *clauses) -> BookingRequest | None:
    return await db.scalar(
        select(BookingRequest)
        .where(BookingRequest.clinic_id == clinic_id, *clauses)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def _queue_email(
    db: AsyncSession,
    clinic_id: UUID,
    item: BookingRequest,
    notification_type: str,
    **extra: object,
) -> None:
    """Queue a message with the notifications gateway in the caller's transaction.

    The requester is not a patient, so only the recipient address is passed.
    Both messages answer the requester's own action: ``force_send`` skips the
    clinic's per-type enable/auto-send switches, and the channel is pinned to
    email whatever channel the clinic prefers for patient reminders.
    """
    clinic = await db.get(Clinic, clinic_id)
    context = {
        "patient_name": item.contact_name,
        "clinic_name": clinic.name if clinic else "DentalPin",
        "clinic_phone": clinic.phone if clinic else None,
        "clinic_address": clinic.address if clinic else None,
        **appointment_when_context(item.start_time, clinic),
        **extra,
    }
    queued = await NotificationGateway.enqueue(
        db,
        clinic_id,
        notification_type,
        context=context,
        to_address=item.contact_email,
        channels=["email"],
        force_send=True,
        dedup_key=f"online_booking:{notification_type}:{item.id}",
    )
    if queued is not None and queued.status == "skipped":
        raise BookingUnavailableError("Email delivery unavailable")


class BookingService:
    """Clinic-scoped booking operations; HTTP transport is handled by the router."""

    @staticmethod
    async def public_settings(db: AsyncSession, clinic_id: UUID) -> BookingSettings:
        config = await db.get(BookingSettings, clinic_id)
        if (
            config is None
            or not config.enabled
            or not config.public_url
            or not config.professional_id
            or not await bookable_professional(db, clinic_id, config.professional_id)
        ):
            raise BookingNotFoundError("Booking unavailable")
        return config

    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> SettingsInput:
        config = await db.get(BookingSettings, clinic_id)
        if config is None:
            return SettingsInput()
        return SettingsInput.model_validate(config, from_attributes=True)

    @staticmethod
    async def update_settings(db: AsyncSession, clinic_id: UUID, data: SettingsInput):
        if data.enabled and (not data.public_url or not data.professional_id):
            raise BookingValidationError("A public URL and professional are required")
        if data.professional_id and not await AppointmentService.validate_professional_access(
            db, clinic_id, data.professional_id
        ):
            raise BookingValidationError("Invalid professional")
        # Enabling for an inactive user would leave the public page unavailable.
        if data.enabled and not await bookable_professional(db, clinic_id, data.professional_id):
            raise BookingValidationError("Invalid professional")
        await lock_clinic(db, clinic_id)
        config = await db.get(BookingSettings, clinic_id)
        if config is None:
            config = BookingSettings(clinic_id=clinic_id)
            db.add(config)
        for key, value in data.model_dump().items():
            setattr(config, key, value)
        await db.flush()
        return data

    @staticmethod
    async def public_config(db: AsyncSession, clinic_id: UUID) -> dict:
        config = await BookingService.public_settings(db, clinic_id)
        return {
            "slot_minutes": config.slot_minutes,
            "timezone": await ClinicHoursService.get_clinic_timezone(db, clinic_id),
            "reasons": ["first_visit", "checkup"],
        }

    @staticmethod
    async def availability(db: AsyncSession, clinic_id: UUID, day: date) -> dict:
        config = await BookingService.public_settings(db, clinic_id)
        starts = await slots(db, clinic_id, config, day, datetime.now(UTC))
        return {
            "starts": [start.isoformat() for start in starts],
            "slot_minutes": config.slot_minutes,
        }

    @staticmethod
    async def create_request(db: AsyncSession, clinic_id: UUID, data: RequestInput) -> str:
        config = await BookingService.public_settings(db, clinic_id)
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
            raise BookingRateLimitedError("Too many requests")
        token = secrets.token_urlsafe(32)
        start = data.start_time.astimezone(UTC)
        item = BookingRequest(
            clinic_id=clinic_id,
            professional_id=config.professional_id,
            start_time=start,
            end_time=start + timedelta(minutes=config.slot_minutes),
            status="pending_confirmation",
            contact_name=data.contact_name,
            contact_email=email,
            contact_phone=data.contact_phone,
            reason=data.reason,
            confirmation_deadline=now + timedelta(minutes=CONFIRMATION_MINUTES),
            token_hash=digest(token),
        )
        await reserve(db, clinic_id, config, item, now)
        # The client-side confirmation page must consume the fragment explicitly.
        await _queue_email(
            db,
            clinic_id,
            item,
            "booking_confirmation",
            confirm_url=f"{config.public_url}#token={token}",
            expires_minutes=CONFIRMATION_MINUTES,
        )
        return "Your confirmation email has been queued."

    @staticmethod
    async def confirm(db: AsyncSession, clinic_id: UUID, token: str) -> str:
        await BookingService.public_settings(db, clinic_id)
        await lock_clinic(db, clinic_id)
        item = await _locked_request(db, clinic_id, BookingRequest.token_hash == digest(token))
        now = datetime.now(UTC)
        if (
            item is None
            or item.status != "pending_confirmation"
            or item.confirmation_deadline <= now
            or item.start_time <= now
        ):
            raise BookingGoneError("Confirmation link expired or invalid")
        if await occupied(
            db,
            clinic_id,
            item.start_time,
            item.end_time,
            now,
            professional_id=item.professional_id,
            exclude=item.id,
        ):
            raise BookingConflictError(SLOT_OCCUPIED)
        item.status = "confirmed"
        item.token_hash = None
        await db.flush()
        return "confirmed"

    @staticmethod
    async def count_confirmed(db: AsyncSession, clinic_id: UUID) -> int:
        total = await db.scalar(
            select(func.count())
            .select_from(BookingRequest)
            .where(
                BookingRequest.clinic_id == clinic_id,
                BookingRequest.status == "confirmed",
                BookingRequest.start_time > datetime.now(UTC),
            )
        )
        return total or 0

    @staticmethod
    async def list_requests(db: AsyncSession, clinic_id: UUID, page: int) -> tuple[list[dict], int]:
        now = datetime.now(UTC)
        total = await db.scalar(
            select(func.count())
            .select_from(BookingRequest)
            .where(BookingRequest.clinic_id == clinic_id, live_hold(now))
        )
        rows = (
            await db.scalars(
                select(BookingRequest)
                .where(BookingRequest.clinic_id == clinic_id, live_hold(now))
                .order_by(BookingRequest.start_time, BookingRequest.id)
                .offset((page - 1) * PAGE_SIZE)
                .limit(PAGE_SIZE)
            )
        ).all()
        config = await db.get(BookingSettings, clinic_id)
        items = [
            {
                "id": row.id,
                "status": row.status,
                "start_time": row.start_time,
                "end_time": row.end_time,
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
            for row in rows
        ]
        return items, total or 0

    @staticmethod
    async def patient_suggestions(db: AsyncSession, clinic_id: UUID, request_id: UUID):
        row = await db.scalar(
            select(BookingRequest).where(
                BookingRequest.id == request_id, BookingRequest.clinic_id == clinic_id
            )
        )
        if row is None:
            raise BookingNotFoundError("Request not found")
        matches = []
        if row.contact_email:
            matches.append(func.lower(Patient.email) == row.contact_email.strip().lower())
        phone = re.sub(r"\D", "", row.contact_phone or "")
        if phone:
            matches.append(func.regexp_replace(Patient.phone, "[^0-9]", "", "g") == phone)
        if not matches:
            return []
        return (
            await db.scalars(
                select(Patient)
                .where(
                    Patient.clinic_id == clinic_id,
                    Patient.status != "archived",
                    or_(*matches),
                )
                .order_by(Patient.first_name, Patient.last_name, Patient.id)
                .limit(10)
            )
        ).all()

    @staticmethod
    async def accept(db: AsyncSession, ctx, request_id: UUID, data: AcceptInput) -> dict:
        for permission in ("agenda.appointments.write", "patients.write"):
            if not await has_permission_for(db, ctx.clinic_id, ctx.role, permission):
                raise BookingForbiddenError(f"Permission denied: {permission}")
        await lock_clinic(db, ctx.clinic_id)
        row = await _locked_request(db, ctx.clinic_id, BookingRequest.id == request_id)
        now = datetime.now(UTC)
        if row is None:
            raise BookingNotFoundError("Request not found")
        if row.status != "confirmed" or row.start_time <= now:
            raise BookingConflictError("Request cannot be accepted")
        if not await bookable_professional(db, ctx.clinic_id, data.professional_id):
            raise BookingValidationError("Invalid professional")
        if data.cabinet_id:
            cabinet = await CabinetService.get_cabinet(db, ctx.clinic_id, data.cabinet_id)
            if not cabinet or not cabinet.is_active:
                raise BookingValidationError("Invalid cabinet")
        end_time = row.start_time + timedelta(minutes=data.duration_minutes)
        # Reception may choose another professional or a cabinet: check those
        # resources, not the configured one. This request's own hold is excluded.
        if await occupied(
            db,
            ctx.clinic_id,
            row.start_time,
            end_time,
            now,
            professional_id=data.professional_id,
            cabinet_id=data.cabinet_id,
            exclude=row.id,
        ):
            raise BookingConflictError(SLOT_OCCUPIED)
        if data.patient_id:
            if not await AppointmentService.validate_patient_access(
                db, ctx.clinic_id, data.patient_id
            ):
                raise BookingNotFoundError("Patient not found")
            patient_id = data.patient_id
        else:
            # Same rule as PatientCreate/PatientUpdate: a patient created here
            # without a surname could not be edited afterwards (#1044).
            if not data.first_name or not data.last_name:
                raise BookingValidationError("Enter a first name and a surname")
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
            raise BookingConflictError(SLOT_OCCUPIED) from exc
        row.status = "accepted"
        row.end_time = end_time
        row.decided_at = now
        row.patient_id = patient_id
        row.appointment_id = appt.id
        await db.flush()
        return {"status": "accepted", "appointment_id": appt.id}

    @staticmethod
    async def reject(db: AsyncSession, ctx, request_id: UUID, data: RejectInput) -> str:
        await lock_clinic(db, ctx.clinic_id)
        row = await _locked_request(db, ctx.clinic_id, BookingRequest.id == request_id)
        if row is None:
            raise BookingNotFoundError("Request not found")
        now = datetime.now(UTC)
        if (
            row.status not in ("pending_confirmation", "confirmed")
            or row.status == "pending_confirmation"
            and row.confirmation_deadline <= now
            or row.status == "confirmed"
            and row.start_time <= now
        ):
            raise BookingConflictError("Request expired or already decided")
        if row.contact_email:
            await _queue_email(
                db, ctx.clinic_id, row, "booking_rejection", rejection_message=data.message
            )
        row.status = "rejected"
        row.decided_at = now
        row.token_hash = None
        row.rejection_message = data.message
        await db.flush()
        return "rejected"
