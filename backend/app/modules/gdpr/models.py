"""GDPR compliance entity models.

GDPR (EU 2016/679) subject-related records for a clinic: data-subject
requests (DSR) with a 30-day SLA, patient consents, retention policies,
the erasure audit log, and data-breach reports. All rows are hard-filtered
by ``clinic_id`` for multi-tenancy.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic
    from app.modules.patients.models import Patient


class GdprRequest(Base, TimestampMixin):
    """A data-subject request (Art. 15-20 GDPR) — v1 is a ticket tracker.

    Status lifecycle: ``received`` -> ``in_progress`` -> ``completed`` (one
    of ``access``/``rectification``/``erasure``/``portability``/``restrict``
    subtypes), or ``rejected`` (Art. 12(5)). ``rectification`` and
    ``restrict`` track the request but do not mutate the patient record in
    v1; objection (Art. 21) has no request type yet. A 30-day deadline is
    derived from ``received_at`` and surfaced via ``SlaCalculator``.
    DSR rows are never deleted (accountability, Art. 5(2)).
    """

    __tablename__ = "gdpr_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"), index=True, nullable=True
    )
    # The requester is whoever asked: the patient themselves or a
    # representative. Stored as text because a request can arrive for a
    # non-patient (e.g. a prospective patient) and pre-empt accounts.
    requester_name: Mapped[str] = mapped_column(String(200))
    requester_email: Mapped[str] = mapped_column(String(255))
    request_type: Mapped[str] = mapped_column(
        String(20)
    )  # access|rectification|erasure|portability|restrict
    status: Mapped[str] = mapped_column(
        String(20), default="received"
    )  # received|in_progress|completed|rejected
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
    patient: Mapped[Patient] = relationship(foreign_keys=[patient_id])


class PatientConsent(Base, TimestampMixin):
    """A single recorded consent/withdrawal for one patient (Art. 7 - 8)."""

    __tablename__ = "patient_consents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    # Processor / processing purpose this consent covers, e.g. "sms", "email",
    # "third_party_sharing", "research".
    purpose: Mapped[str] = mapped_column(String(100))
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Text shown to the data subject at consent time (Art. 4(11) consent must
    # be informed). Kept verbatim so withdrawal disputes can be settled.
    provided_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
    patient: Mapped[Patient] = relationship(foreign_keys=[patient_id])


class RetentionPolicy(Base, TimestampMixin):
    """Retention rules that gate erasure eligibility (Art. 5(1)(e))."""

    __tablename__ = "retention_policies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    # Data category the rule applies to. Only the closed erasure
    # vocabulary (email | phone | identity — see schemas.ErasureCategory)
    # can ever be erased; policies for other categories (e.g. "clinical",
    # "billing", "radiology") document the hold and always retain.
    # Scoped per clinic so each clinic can set its own legal hold periods.
    data_category: Mapped[str] = mapped_column(String(100))
    retention_years: Mapped[int] = mapped_column(Integer)
    # Optional extra hold (e.g. a litigation hold). When set, erasure waits
    # until this date regardless of ``retention_years``.
    legal_hold_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])


class ErasureAuditLog(Base, TimestampMixin):
    """Immutable log of every partial-erasure that ran (Art. 17 accountability)."""

    __tablename__ = "gdpr_erasure_audit_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"), index=True, nullable=True
    )
    # UUID of the DSR (if any) that triggered this erasure; kept as a
    # snapshot so the audit trail reads cleanly. Not an FK constraint —
    # an erasure can be run directly by an agent without a request
    # record. (DSR rows themselves are never deleted.)
    request_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Categories erased (subset of the retention data_categories), stored as a
    # JSON array for auditability.
    erased_categories: Mapped[list] = mapped_column(JSON, default=list)
    # Snapshot of which identifiers were blanked, keyed by category.
    fields_blanked: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # UUID of the operator/agent who ran the erasure (audit attribution).
    executed_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])


class DataBreach(Base, TimestampMixin):
    """A reportable personal-data breach (Art. 33-34)."""

    __tablename__ = "data_breaches"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    description: Mapped[str] = mapped_column(Text)
    data_involved: Mapped[list] = mapped_column(JSON, default=list)
    affected_people: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Regulatory status: under_review | reported | not_reportable |
    # resolved.
    status: Mapped[str] = mapped_column(String(20), default="under_review")
    notified_authority_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reported: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
