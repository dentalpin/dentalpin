"""Synthetic data builders shared by the online booking tests."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.auth.models import ClinicMembership, User
from app.modules.agenda.models import Appointment
from app.modules.notifications.gateway import NotificationGateway
from app.modules.online_booking.models import BookingSettings


async def dispatch(db) -> int:
    """Commit, then let the notifications outbox deliver what was queued."""
    await db.commit()
    return await NotificationGateway.dispatch_outbox(db)


async def clinic_user(db, clinic_id: UUID) -> UUID:
    return await db.scalar(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic_id)
    )


async def professional(db, clinic_id: UUID) -> User:
    from app.core.auth.service import hash_password

    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.invalid",
        password_hash=hash_password("Synthetic123!"),
        first_name="Test",
        last_name="Professional",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(
        ClinicMembership(
            id=uuid4(), user_id=user.id, clinic_id=clinic_id, role="dentist", is_professional=True
        )
    )
    await db.flush()
    return user


async def configure(db, clinic_id: UUID, professional_id: UUID) -> BookingSettings:
    config = await db.get(BookingSettings, clinic_id)
    if config is None:
        config = BookingSettings(clinic_id=clinic_id)
        db.add(config)
    config.enabled = True
    config.professional_id = professional_id
    config.public_url = "https://example.invalid/book"
    config.slot_minutes = 30
    config.window_days = 30
    config.min_notice_minutes = 0
    await db.commit()
    return config


def appointment(clinic_id, professional_id, start, minutes=30, cabinet_id=None) -> Appointment:
    return Appointment(
        clinic_id=clinic_id,
        professional_id=professional_id,
        cabinet_id=cabinet_id,
        start_time=start,
        end_time=start + timedelta(minutes=minutes),
        status="scheduled",
    )


def tomorrow_at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine((datetime.now(UTC) + timedelta(days=1)).date(), time(hour, minute), UTC)
