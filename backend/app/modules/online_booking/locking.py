"""Transaction-scoped locks for online booking writers.

The lock only coordinates code paths that acquire the same key. Agenda's
independent writers do not acquire it (dentalpin/dentalpin#905).
"""

from hashlib import blake2b
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def clinic_lock_key(clinic_id: UUID) -> int:
    """Return a stable, namespaced PostgreSQL signed bigint for one clinic."""
    digest = blake2b(b"online_booking:clinic:" + clinic_id.bytes, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


async def lock_clinic(db: AsyncSession, clinic_id: UUID) -> None:
    """Serialize cooperating writers through the end of their transaction."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": clinic_lock_key(clinic_id)},
    )
