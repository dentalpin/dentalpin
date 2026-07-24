"""medical_reference — clinic-managed lookup lists backing the searchable
comboboxes in patients_clinical's allergy/medication/systemic-disease/
surgery inputs, plus known medication-medication interactions and
disease-medication contraindications used to actively flag a patient's
recorded medical history (see MedicalReferenceService.get_patient_flags).

Soft-delete only (``is_active``): a reference item that's been used on a
patient record must never disappear from history, so retiring an item
just hides it from future searches rather than deleting the row.

ReferenceInteraction/ReferenceContraindication link to other tables in
*this same module* by real FK — safe, since that's intra-module, unlike
the loose (FK-less) link from patients_clinical's Allergy/Medication/
SystemicDisease/SurgicalHistory back to here.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
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


class ReferenceSurgery(Base, TimestampMixin):
    __tablename__ = "medical_reference_surgery"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_medical_reference_surgery_clinic_name"),
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


class ReferenceInteraction(Base, TimestampMixin):
    """Known interaction between two specific reference medications.

    ``medication_a_id``/``medication_b_id`` are always stored with
    ``medication_a_id < medication_b_id`` (string-sorted) so a pair only
    ever exists in one canonical order — the unique constraint then
    reliably prevents storing the same pair twice regardless of which
    order they were entered in. Enforced in service.py, not the DB.
    """

    __tablename__ = "medical_reference_interaction"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    medication_a_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_reference_medication.id"), index=True
    )
    medication_b_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_reference_medication.id"), index=True
    )
    risk_note: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "medication_a_id",
            "medication_b_id",
            name="uq_medical_reference_interaction_pair",
        ),
    )


class ReferenceContraindication(Base, TimestampMixin):
    """A specific reference disease contraindicating a specific reference
    medication — the source of the active per-patient flag."""

    __tablename__ = "medical_reference_contraindication"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    disease_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_reference_disease.id"), index=True
    )
    medication_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_reference_medication.id"), index=True
    )
    risk_note: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "disease_id",
            "medication_id",
            name="uq_medical_reference_contraindication_pair",
        ),
    )
