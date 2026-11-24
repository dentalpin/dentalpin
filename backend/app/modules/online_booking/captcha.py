"""ALTCHA v2 challenges, bound to a clinic and consumed once transactionally."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from altcha import Payload, create_challenge, verify_solution
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from .exceptions import CaptchaInvalidError, CaptchaReusedError
from .models import BookingRateLimit


def _secret(clinic_id: UUID) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), b"online_booking:altcha:" + clinic_id.bytes, hashlib.sha256
    ).hexdigest()


def challenge(clinic_id: UUID) -> dict:
    return create_challenge(
        algorithm="PBKDF2/SHA-256",
        cost=1000,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        data={"clinic": str(clinic_id)},
        hmac_secret=_secret(clinic_id),
    ).to_dict()


async def consume(db: AsyncSession, clinic_id: UUID, encoded: str) -> None:
    try:
        proof = Payload.from_base64(encoded)
        params = proof.challenge.parameters
        now = datetime.now(UTC)
        if (
            params.algorithm != "PBKDF2/SHA-256"
            or params.cost != 1000
            or params.data != {"clinic": str(clinic_id)}
            or not isinstance(params.expires_at, int)
            or params.expires_at < now.timestamp()
            or params.expires_at > (now + timedelta(minutes=10)).timestamp()
            or not proof.challenge.signature
            or not verify_solution(proof, _secret(clinic_id)).verified
        ):
            raise ValueError("Invalid challenge")
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        raise CaptchaInvalidError("Verification failed") from None
    key = hashlib.sha256(("altcha:" + proof.challenge.signature).encode()).hexdigest()
    result = await db.scalar(
        insert(BookingRateLimit)
        .values(key=key, window_start=datetime.fromtimestamp(params.expires_at, UTC), attempts=1)
        .on_conflict_do_nothing(
            index_elements=[BookingRateLimit.key, BookingRateLimit.window_start]
        )
        .returning(BookingRateLimit.key)
    )
    if result is None:
        raise CaptchaReusedError("Verification already used")
