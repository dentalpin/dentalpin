"""Retention cleanup, registered only when the module is installed."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update

from app.database import async_session_maker

from .models import BookingRateLimit, BookingRequest


async def cleanup() -> None:
    now = datetime.now(UTC)
    async with async_session_maker() as db:
        await db.execute(
            update(BookingRequest)
            .where(
                BookingRequest.status == "pending_confirmation",
                BookingRequest.confirmation_deadline <= now,
            )
            .values(
                status="expired", decided_at=BookingRequest.confirmation_deadline, token_hash=None
            )
        )
        await db.execute(
            update(BookingRequest)
            .where(BookingRequest.status == "confirmed", BookingRequest.start_time <= now)
            .values(status="expired", decided_at=BookingRequest.start_time, token_hash=None)
        )
        await db.execute(
            delete(BookingRequest).where(
                BookingRequest.status.in_(("rejected", "expired")),
                BookingRequest.decided_at <= now - timedelta(days=30),
            )
        )
        await db.execute(
            update(BookingRequest)
            .where(
                BookingRequest.status == "accepted",
                BookingRequest.decided_at <= now - timedelta(days=90),
            )
            .values(contact_name=None, contact_email=None, contact_phone=None, token_hash=None)
        )
        await db.execute(
            delete(BookingRateLimit).where(BookingRateLimit.window_start < now - timedelta(hours=2))
        )
        await db.commit()
