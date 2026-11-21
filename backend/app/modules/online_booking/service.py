"""Availability and transactional lifecycle for online booking.

Availability is that of the one professional configured in the settings: the
``schedules`` module supplies their hours, and only their active appointments
and live holds block a slot. Other professionals' appointments never do. On
acceptance reception may pick another professional or a cabinet; the overlap
check then runs for the chosen resources.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.agenda.locks import lock_clinic
from app.modules.agenda.models import Appointment
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.service import appointment_when_context
from app.modules.schedules.services.availability import AvailabilityService

from .models import BookingRequest, BookingSettings

ACTIVE = ("scheduled", "confirmed", "checked_in", "in_treatment")


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
    if not config.enabled or config.professional_id is None:
        raise ValueError("Booking is disabled")
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
        raise ValueError("Time slot is no longer available")
    db.add(item)
    await db.flush()


async def queue_email(
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
        raise HTTPException(503, "Email delivery unavailable")
