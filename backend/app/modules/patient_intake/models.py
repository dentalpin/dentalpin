"""Clinic-scoped configuration, intake submissions and consent provenance."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class FormVersion(Base, TimestampMixin):
    __tablename__ = "patient_intake_form_versions"
    __table_args__ = (UniqueConstraint("clinic_id", "locale", "version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    published_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(10))
    definition: Mapped[dict] = mapped_column(JSONB)


class Intake(Base, TimestampMixin):
    __tablename__ = "patient_intake_submissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    form_id: Mapped[UUID] = mapped_column(ForeignKey("patient_intake_form_versions.id"))
    issued_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    representative: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answers: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    administrative_review: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    clinical_review: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentProvenance(Base):
    __tablename__ = "patient_intake_consent_provenance"

    # The consent and provenance are appended in one transaction.
    # The ledger UUID is a soft reference so a GDPR branch rollback
    # never drops retained intake data.
    consent_id: Mapped[UUID] = mapped_column(primary_key=True)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    intake_id: Mapped[UUID | None] = mapped_column(ForeignKey("patient_intake_submissions.id"))
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
