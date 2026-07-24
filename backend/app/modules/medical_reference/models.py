"""medical_reference — clinic-managed lookup lists backing the searchable
comboboxes in patients_clinical's allergy/medication/systemic-disease
inputs. Deliberately independent of ``patients`` — this is pure reference
data, not per-patient data (``depends: []`` in the manifest).

Soft-delete only (``is_active``): a reference item that's been used on a
patient record must never disappear from history, so retiring an item
just hides it from future searches rather than deleting the row.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class ReferenceAllergy(Base, TimestampMixin):
    __tablename__ = "medical_reference_allergy"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_medical_reference_allergy_clinic_name"),
    )


class ReferenceMedication(Base, TimestampMixin):
    __tablename__ = "medical_reference_medication"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_medical_reference_medication_clinic_name"),
    )


class ReferenceDisease(Base, TimestampMixin):
    """Systemic disease reference entry. ``is_apci`` marks it as being on
    the clinic's Liste des Affections Prises en Charge Intégralement —
    the flag that drives the auto-computed APCI coverage indicator."""

    __tablename__ = "medical_reference_disease"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    is_apci: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_medical_reference_disease_clinic_name"),
    )
