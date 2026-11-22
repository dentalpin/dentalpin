"""Cross-worker fixed-hour limits with pseudonymous, expiring keys."""

import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import async_session_maker

from .models import BookingRateLimit


async def consume_rate(kind: str, identity: str, maximum: int) -> None:
    digest = hmac.new(
        settings.SECRET_KEY.encode(), f"online_booking:{kind}:{identity}".encode(), hashlib.sha256
    ).hexdigest()
    window = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    statement = insert(BookingRateLimit).values(key=digest, window_start=window, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=[BookingRateLimit.key, BookingRateLimit.window_start],
        set_={"attempts": BookingRateLimit.attempts + 1},
    ).returning(BookingRateLimit.attempts)
    async with async_session_maker() as db:
        count = await db.scalar(statement)
        await db.commit()
    if count > maximum:
        raise HTTPException(429, "Too many requests")
