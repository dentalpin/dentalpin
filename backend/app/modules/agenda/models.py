"""Agenda models — appointments + linked treatments + cabinets."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

# Canonical status set. Mirrored in the frontend composable
# ``useAppointmentStatus.ts`` and kept in sync via a parity test.
APPOINTMENT_STATUSES: tuple[str, ...] = (
    "scheduled",
    "confirmed",
    "checked_in",
    "in_treatment",
    "completed",
    "cancelled",
    "no_show",
)

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User
    from app.modules.patients.models import Patient


class Cabinet(Base, TimestampMixin):
    """Cabinet (physical scheduling slot) belonging to a clinic.

    Fase B.2 chunk 3 promoted cabinets from a JSONB column on
    ``clinic.cabinets`` to their own table with referential integrity.
    """

    __tablename__ = "cabinets"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(7))  # Hex color
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    clinic: Mapped[Clinic] = relationship(back_populates="cabinets")

    __table_args__ = (
        Index(
            "uq_cabinet_clinic_name",
            "clinic_id",
            "name",
            unique=True,
        ),
    )


class Appointment(Base, TimestampMixin):
    """Appointment entity."""

    __tablename__ = "appointments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"))
    professional_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assistant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Denormalized cabinet name (kept in sync on Cabinet rename). The
    # authoritative reference is ``cabinet_id`` — the string lets
    # legacy filters keep working during the frontend migration.
    # Both are nullable: a booked appointment may exist without a cabinet
    # decision until the patient arrives. The cabinet is assigned on the
    # kanban board when transitioning to ``in_treatment``.
    cabinet: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cabinet_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cabinets.id"), index=True, nullable=True
    )
    # When / by whom the current cabinet was last assigned. Denormalized
    # from ``appointment_cabinet_events``; kept in sync by
    # :meth:`AppointmentService.assign_cabinet`.
    cabinet_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cabinet_assigned_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    treatment_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    # Timestamp of the latest status transition. Denormalized so the
    # calendar can render "waiting 12 min" without joining the history
    # table on every card. Kept in sync by ``AppointmentService.transition``.
    current_status_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    color: Mapped[str | None] = mapped_column(String(7))

    clinic: Mapped[Clinic] = relationship(back_populates="appointments")
    # No ``back_populates`` — patients is foundational and cannot
    # reference consumer modules. The relationship stays
    # one-directional (Appointment → Patient).
    patient: Mapped[Patient | None] = relationship()
    professional: Mapped[User] = relationship(foreign_keys=[professional_id])
    assistant: Mapped[User | None] = relationship(foreign_keys=[assistant_id])
    cabinet_assigner: Mapped[User | None] = relationship(foreign_keys=[cabinet_assigned_by])
    cabinet_ref: Mapped[Cabinet | None] = relationship()

    # ``treatments`` is installed by treatment_plan's AppointmentTreatment
    # backref (#337): the link table is plan-owned (its planned-item FK is
    # NOT NULL), and this direction of the dependency is the undeclarable
    # one (#309). Agenda reads it duck-typed; eager loading goes through
    # the planned-work provider.

    status_events: Mapped[list[AppointmentStatusEvent]] = relationship(
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="AppointmentStatusEvent.changed_at",
    )

    cabinet_events: Mapped[list[AppointmentCabinetEvent]] = relationship(
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="AppointmentCabinetEvent.changed_at",
    )

    __table_args__ = (
        Index(
            "idx_appointment_slot",
            "clinic_id",
            "cabinet_id",
            "professional_id",
            "start_time",
            unique=True,
            postgresql_where=(status != "cancelled"),
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in APPOINTMENT_STATUSES) + ")",
            name="ck_appointment_status_valid",
        ),
    )


class AppointmentStatusEvent(Base):
    """Append-only audit trail for appointment status transitions.

    One row per transition. ``from_status`` is NULL only for the synthetic
    "created" event (first row for each appointment). ``changed_by`` is
    nullable to tolerate backfill rows from the initial migration where
    the acting user cannot be recovered.
    """

    __tablename__ = "appointment_status_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    appointment_id: Mapped[UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    appointment: Mapped[Appointment] = relationship(back_populates="status_events")
    actor: Mapped[User | None] = relationship()

    __table_args__ = (
        Index(
            "ix_appointment_status_events_appointment_changed_at",
            "appointment_id",
            "changed_at",
        ),
    )


class AppointmentCabinetEvent(Base):
    """Append-only audit trail for cabinet assignments.

    Kept separate from ``appointment_status_events`` so analytics queries
    stay simple (one event table per concern). ``from_cabinet_id`` is NULL
    on the very first assignment; ``to_cabinet_id`` is NULL on an unassign.
    """

    __tablename__ = "appointment_cabinet_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    appointment_id: Mapped[UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    from_cabinet_id: Mapped[UUID | None] = mapped_column(ForeignKey("cabinets.id"), nullable=True)
    to_cabinet_id: Mapped[UUID | None] = mapped_column(ForeignKey("cabinets.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    appointment: Mapped[Appointment] = relationship(back_populates="cabinet_events")
    actor: Mapped[User | None] = relationship(foreign_keys=[changed_by])
    from_cabinet: Mapped[Cabinet | None] = relationship(foreign_keys=[from_cabinet_id])
    to_cabinet: Mapped[Cabinet | None] = relationship(foreign_keys=[to_cabinet_id])

    __table_args__ = (
        Index(
            "ix_appointment_cabinet_events_appointment_changed_at",
            "appointment_id",
            "changed_at",
        ),
    )
