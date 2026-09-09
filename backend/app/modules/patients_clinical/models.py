"""Normalized medical history + emergency contact models.

Replaces the JSONB blobs (``patients.medical_history``,
``patients.emergency_contact``, ``patients.legal_guardian``) that
lived directly on the patient row before Fase B.4.

Table names are prefixed ``patients_clinical_`` so analytics queries
stay unambiguous across modules.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.patients.models import Patient


class MedicalContext(Base, TimestampMixin):
    """1:1 medical flags + anesthesia + lifestyle context for a patient."""

    __tablename__ = "patients_clinical_medical_context"

    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    is_pregnant: Mapped[bool] = mapped_column(Boolean, default=False)
    pregnancy_week: Mapped[int | None] = mapped_column(Integer)
    is_lactating: Mapped[bool] = mapped_column(Boolean, default=False)

    is_on_anticoagulants: Mapped[bool] = mapped_column(Boolean, default=False)
    anticoagulant_medication: Mapped[str | None] = mapped_column(String(100))
    inr_value: Mapped[float | None] = mapped_column(Float)
    last_inr_date: Mapped[date | None] = mapped_column(Date)

    is_smoker: Mapped[bool] = mapped_column(Boolean, default=False)
    smoking_frequency: Mapped[str | None] = mapped_column(String(100))
    alcohol_consumption: Mapped[str | None] = mapped_column(String(100))

    bruxism: Mapped[bool] = mapped_column(Boolean, default=False)

    adverse_reactions_to_anesthesia: Mapped[bool] = mapped_column(Boolean, default=False)
    anesthesia_reaction_details: Mapped[str | None] = mapped_column(String(500))

    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    patient: Mapped[Patient] = relationship()


class Allergy(Base, TimestampMixin):
    """Individual allergy entry (N:1 patient)."""

    __tablename__ = "patients_clinical_allergy"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str | None] = mapped_column(String(50))
    # severity: low | medium | high | critical
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    reaction: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    # Loose link to medical_reference.ReferenceAllergy — a plain nullable
    # UUID, deliberately NOT a DB-level FK, so this module stays fully
    # standalone if the optional medical_reference module is uninstalled
    # (see pc_0002 migration).
    reference_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    # Soft-delete (house rule: never hard-delete patient data). Deletes set
    # this to "archived"; lists filter to "active", gets return the row.
    status: Mapped[str] = mapped_column(String(20), default="active")


class Medication(Base, TimestampMixin):
    """Medication the patient is currently taking (N:1)."""

    __tablename__ = "patients_clinical_medication"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(100))
    dosage: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    # Loose (FK-less) link to medical_reference.ReferenceMedication.
    reference_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    # Soft-delete (house rule: never hard-delete patient data).
    status: Mapped[str] = mapped_column(String(20), default="active")


class SystemicDisease(Base, TimestampMixin):
    """Systemic disease / condition (N:1)."""

    __tablename__ = "patients_clinical_systemic_disease"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str | None] = mapped_column(String(50))
    diagnosis_date: Mapped[date | None] = mapped_column(Date)
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    medications: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Loose (FK-less) link to medical_reference.ReferenceDisease.
    reference_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    # Soft-delete (house rule: never hard-delete patient data).
    status: Mapped[str] = mapped_column(String(20), default="active")


class SurgicalHistory(Base, TimestampMixin):
    """Past surgery / procedure (N:1)."""

    __tablename__ = "patients_clinical_surgical_history"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    procedure: Mapped[str] = mapped_column(String(200))
    surgery_date: Mapped[date | None] = mapped_column(Date)
    complications: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Loose (FK-less) link to medical_reference.ReferenceSurgery.
    reference_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    # Soft-delete (house rule: never hard-delete patient data).
    status: Mapped[str] = mapped_column(String(20), default="active")


class EmergencyContact(Base, TimestampMixin):
    """Emergency contact (1:1)."""

    __tablename__ = "patients_clinical_emergency_contact"

    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(100))
    relationship: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    is_legal_guardian: Mapped[bool] = mapped_column(Boolean, default=False)

    # Soft-delete (house rule: never hard-delete patient data). Upserts
    # revive an archived row (PK is patient_id, so no second row is possible).
    status: Mapped[str] = mapped_column(String(20), default="active")


class LegalGuardian(Base, TimestampMixin):
    """Legal guardian (1:1, for minors or incapacitated patients)."""

    __tablename__ = "patients_clinical_legal_guardian"

    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(100))
    relationship: Mapped[str] = mapped_column(String(50))
    dni: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    # Soft-delete (house rule: never hard-delete patient data). Upserts
    # revive an archived row (PK is patient_id, so no second row is possible).
    status: Mapped[str] = mapped_column(String(20), default="active")
