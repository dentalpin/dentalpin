"""LabOrder entity — a piece of work sent to an external lab for a patient.

Cross-branch FKs to ``patients`` and ``contacts`` are allowed because both
are listed in this module's ``manifest.depends`` (see ADR 0002 / 0003).
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

WORK_TYPES = ("crown", "bridge", "denture", "implant", "veneer", "orthodontic", "other")
ORDER_STATUSES = ("sent", "in_progress", "ready", "received", "cancelled")


class LabOrder(Base, TimestampMixin):
    """A work order sent to an external lab for a specific patient."""

    __tablename__ = "lab_orders"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    lab_contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), index=True)

    work_type: Mapped[str] = mapped_column(String(20), index=True)
    tooth_reference: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), index=True, default="sent")

    sent_date: Mapped[date] = mapped_column(Date)
    expected_date: Mapped[date | None] = mapped_column(Date)
    received_date: Mapped[date | None] = mapped_column(Date)

    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
