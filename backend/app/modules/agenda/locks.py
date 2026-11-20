"""Transaction-scoped coordination for writers that change the agenda."""

from hashlib import blake2b
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_clinic(db: AsyncSession, clinic_id: UUID) -> None:
    """Serialize agenda writers until the caller commits or rolls back."""
    # Keep the online booking namespace so both modules take the same key.
    digest = blake2b(b"online_booking:clinic:" + clinic_id.bytes, digest_size=8).digest()
    key = int.from_bytes(digest, byteorder="big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": key})
