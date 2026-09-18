"""staff_attendance — clock in/out events for clinic staff.

Append-only event log (in/out per staff user), current-state lookup, and
a daily pairing report. Deliberately NOT shifts, rosters, overtime math,
or payroll linkage — those need their own design (see CLAUDE.md Later).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class AttendanceEvent(Base, TimestampMixin):
    """One clock in/out punch. Immutable once written (no update route)."""

    __tablename__ = "attendance_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)

    # in | out
    kind: Mapped[str] = mapped_column(String(8))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    # Acting user who recorded the punch (from auth, never the body:
    # anyone with the grant could otherwise punch for a colleague).
    # Nullable for rows written before this column existed.
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None, index=True
    )
