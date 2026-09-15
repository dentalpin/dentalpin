"""prescriptions — clinical prescriptions with per-country compliance hooks.

Base module (issue #269): country-agnostic clinical pad. Legal/format
requirements per country ship as localization modules on top (same
pattern as billing → verifactu), registering a
``PrescriptionComplianceHook`` for their ``country_code``.

Lifecycle: issued prescriptions are immutable — corrections are cancel
+ reissue (clinical-legal artifact, invoice rule). Never hard-delete.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class Prescription(Base, TimestampMixin):
    """One clinical prescription. Drafts mutate; issued rows freeze."""

    __tablename__ = "prescriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    prescriber_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)

    # draft | issued | cancelled (terminal states never leave).
    status: Mapped[str] = mapped_column(String(20), default="draft")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    locale: Mapped[str] = mapped_column(String(8), default="es")

    # Prescriber snapshot frozen at issue time (identity must not drift
    # when the profile later changes — legal artifact).
    prescriber_name: Mapped[str | None] = mapped_column(String(200), default=None)
    license_number: Mapped[str | None] = mapped_column(String(100), default=None)
    signature_document_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), default=None)

    # Per-country hook output, keyed by country code (mirrors
    # Invoice.compliance_data).
    compliance_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PrescriptionItem(Base, TimestampMixin):
    """One medication line. Free text always works; catalog_ref is a soft
    link (no FK): autofill when medication_catalog is installed, keeps
    working when it is not."""

    __tablename__ = "prescription_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    prescription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        index=True,
    )
    catalog_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), default=None)
    medication_name: Mapped[str] = mapped_column(String(150))
    dosage: Mapped[str | None] = mapped_column(String(50), default=None)
    unit: Mapped[str | None] = mapped_column(String(20), default=None)
    route: Mapped[str | None] = mapped_column(String(50), default=None)
    frequency: Mapped[str | None] = mapped_column(String(100), default=None)
    duration: Mapped[str | None] = mapped_column(String(100), default=None)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class PrescriptionTemplate(Base, TimestampMixin):
    """Clinic-level favorite combo, stored as JSONB items for one-click fill."""

    __tablename__ = "prescription_templates"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_prescription_templates_clinic_name"),
    )


class PrescriberProfile(Base, TimestampMixin):
    """Per-user defaults for the prescription pad: license number and an
    optional signature image (stored as a media document id, opaque —
    no FK so this module keeps ``depends == ["patients"]``).

    Module-owned table (not core): keeps professional identity out of
    the core user row while country modules override labels via hooks.
    """

    __tablename__ = "prescriber_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    license_number: Mapped[str | None] = mapped_column(String(100), default=None)
    signature_document_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), default=None)

    __table_args__ = (
        UniqueConstraint("clinic_id", "user_id", name="uq_prescriber_profiles_clinic_user"),
    )
