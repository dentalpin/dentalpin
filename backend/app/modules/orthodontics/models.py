"""Orthodontic case + control models (issue #270, slice-a).

Slice-a covers clinical tracking only: cases, per-visit controls,
photo evolution via media attachments, chip-catalog settings seeds.
Slice-b (separate PR) adds the treatment-plan installment link, recall
upsert, and the appointment link — see ``docs/technical/orthodontics/overview.md``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

APPLIANCE_TYPES = (
    "brackets_metal",
    "brackets_esthetic",
    "self_ligating",
    "aligners",
    "functional",
    "retention",
)

CASE_STATUSES = ("active", "paused", "finished", "transferred_out")

HYGIENE_LEVELS = ("good", "fair", "poor")


class OrthoCase(Base):
    __tablename__ = "ortho_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    appliance_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    estimated_months: Mapped[int | None] = mapped_column(nullable=True)
    diagnosis_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_upper_wire: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_lower_wire: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    controls: Mapped[list[OrthoControl]] = relationship(
        "OrthoControl", back_populates="case", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("ix_ortho_cases_clinic_patient", "clinic_id", "patient_id"),)


class OrthoControl(Base):
    __tablename__ = "ortho_controls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ortho_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    upper_wire: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lower_wire: Mapped[str | None] = mapped_column(String(40), nullable=True)
    procedures: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    procedures_other: Mapped[str | None] = mapped_column(Text, nullable=True)
    aligner_number: Mapped[int | None] = mapped_column(nullable=True)
    hygiene: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_control_weeks: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    case: Mapped[OrthoCase] = relationship("OrthoCase", back_populates="controls")

    __table_args__ = (Index("ix_ortho_controls_case_performed", "case_id", "performed_at"),)


class OrthoSettings(Base):
    __tablename__ = "ortho_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, unique=True, index=True
    )
    wires: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    procedures: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
