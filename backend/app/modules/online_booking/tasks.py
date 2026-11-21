"""Retention cleanup, registered only when the module is installed."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import String, cast, delete, func, select, update

from app.database import async_session_maker
from app.modules.notifications.models import CommunicationMessage

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
        # A confirmation still waiting in the gateway outbox is worthless once
        # its request left ``pending_confirmation``: cancel it unsent.
        await db.execute(
            update(CommunicationMessage)
            .where(
                CommunicationMessage.template_key == "booking_confirmation",
                CommunicationMessage.status.in_(("queued", "failed")),
                CommunicationMessage.dedup_key.in_(
                    select(
                        func.concat(
                            "online_booking:booking_confirmation:", cast(BookingRequest.id, String)
                        )
                    ).where(BookingRequest.status != "pending_confirmation")
                ),
            )
            .values(
                status="skipped",
                error_message="booking_request_closed",
                next_attempt_at=None,
                context_data={},
            )
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
