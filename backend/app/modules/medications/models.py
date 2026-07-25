"""Medication catalog entity.

Matches the real ``patients`` module pattern (confirmed against
backend/app/modules/patients/models.py on lamanji/dentalpin@my-version):
Base + TimestampMixin from app.database, clinic_id FK for multi-tenancy.
"""

from __future__ import annotations

from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class UnitType(str, PyEnum):
    mg = "mg"
    g = "g"
    ml = "ml"
    ui = "UI"
    percent = "%"
    other = "other"


class MedicationForm(str, PyEnum):
    tablet = "tablet"
    capsule = "capsule"
    syrup = "syrup"
    gel = "gel"
    mouthwash = "mouthwash"
    injection = "injection"
    cream = "cream"
    other = "other"


class Medication(Base, TimestampMixin):
    """A catalog entry for a drug the clinic prescribes or references."""

    __tablename__ = "medications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    dose: Mapped[float] = mapped_column(Numeric(10, 2))
    unit: Mapped[UnitType] = mapped_column(
        SAEnum(
            UnitType,
            name="medication_unit_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    form: Mapped[MedicationForm] = mapped_column(
        SAEnum(
            MedicationForm,
            name="medication_form",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    times_per_day: Mapped[int | None] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(Text)
    is_prescribed: Mapped[bool] = mapped_column(Boolean, default=True)
