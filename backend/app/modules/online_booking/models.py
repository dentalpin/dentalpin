"""Data owned by the optional public booking module."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class BookingSettings(Base, TimestampMixin):
    __tablename__ = "online_booking_settings"
    clinic_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    public_url: Mapped[str | None] = mapped_column(String(500))
    professional_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    first_visit_minutes: Mapped[int | None] = mapped_column(Integer)
    checkup_minutes: Mapped[int | None] = mapped_column(Integer)
    window_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    min_notice_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    __table_args__ = (
        CheckConstraint("slot_minutes BETWEEN 5 AND 480", name="ck_ob_slot_minutes"),
        CheckConstraint(
            "first_visit_minutes IS NULL OR first_visit_minutes BETWEEN 5 AND 480",
            name="ck_ob_first_visit_minutes",
        ),
        CheckConstraint(
            "checkup_minutes IS NULL OR checkup_minutes BETWEEN 5 AND 480",
            name="ck_ob_checkup_minutes",
        ),
        CheckConstraint("window_days BETWEEN 1 AND 365", name="ck_ob_window_days"),
        CheckConstraint("min_notice_minutes BETWEEN 0 AND 525600", name="ck_ob_notice"),
    )


class BookingRequest(Base, TimestampMixin):
    __tablename__ = "online_booking_requests"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending_confirmation", nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    confirmation_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appointment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL")
    )
    patient_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL")
    )
    rejection_message: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_ob_request_interval"),
        CheckConstraint(
            "status IN ('pending_confirmation','confirmed','accepted','rejected','expired')",
            name="ck_ob_request_status",
        ),
        CheckConstraint("reason IN ('first_visit','checkup')", name="ck_ob_request_reason"),
    )


class BookingRateLimit(Base):
    """Hashed identities and fixed-hour counters shared by all workers."""

    __tablename__ = "online_booking_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
