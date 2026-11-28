"""Recalls module — patient call-back data model.

Three tables:

* ``recalls`` — one row per scheduled call-back.
* ``recall_contact_attempts`` — append-only attempt log per recall.
* ``recall_settings`` — one row per clinic, holding the reason
  intervals + treatment-category → reason map + automation toggles.

Cross-module FKs are restricted to ``patients.id`` and
``appointments.id`` because those are the only modules in
``manifest.depends``. Treatment-plan / catalog references are stored
as snapshots (string + nullable UUID without FK).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    pass


# Enum-as-string values are documented here, not enforced at the DB
# level (matches the rest of the codebase — see ``Patient.status``).

REASONS = (
    "hygiene",
    "checkup",
    "ortho_review",
    "implant_review",
    "post_op",
    "treatment_followup",
    "other",
)

PRIORITIES = ("low", "normal", "high")

STATUSES = (
    "pending",
    "contacted_no_answer",
    "contacted_scheduled",
    "contacted_declined",
    "done",
    "cancelled",
    "needs_review",
)

CHANNELS = ("phone", "whatsapp", "sms", "email")

OUTCOMES = (
    "no_answer",
    "voicemail",
    "scheduled",
    "declined",
    "wrong_number",
)


class Recall(Base, TimestampMixin):
    """Patient call-back row."""

    __tablename__ = "recalls"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )

    # Always day-1 of the target month so monthly buckets index cheaply.
    due_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Optional precise day inside the month, when the dentist wants more
    # granularity (e.g. "the day she comes back from holidays").
    due_date: Mapped[date | None] = mapped_column(Date)

    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_note: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)

    recommended_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_professional_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    last_contact_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    linked_appointment_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id")
    )
    # No FK — treatment_plan is not in manifest.depends. Snapshot only.
    linked_treatment_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    # Snapshot of the catalog category that drove the suggestion (e.g.
    # ``preventivo``). Used by the call list to label the recall and by
    # auto-link logic to match scheduled appointments.
    linked_treatment_category_key: Mapped[str | None] = mapped_column(String(80))

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_recalls_clinic_due_month_status",
            "clinic_id",
            "due_month",
            "status",
        ),
        Index(
            "ix_recalls_clinic_patient_reason_status",
            "clinic_id",
            "patient_id",
            "reason",
            "status",
        ),
    )


class RecallContactAttempt(Base):
    """One row per outbound contact attempt for a recall.

    Append-only — never updated, never soft-deleted, except a GDPR erasure
    that clears ``note`` (#546). ``attempted_at`` is
    server-set so the log is monotonic regardless of client clock skew.
    """

    __tablename__ = "recall_contact_attempts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    recall_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recalls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempted_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class RecallSettings(Base):
    """Per-clinic recall configuration.

    JSONB columns hold:

    * ``reason_intervals`` — ``{reason: months}`` (e.g. ``{"hygiene": 6}``).
    * ``category_to_reason`` — ``{catalog_category_key: reason}`` (e.g.
      ``{"preventivo": "hygiene"}``).

    Lazy-created on first read by ``RecallSettingsService``.
    """

    __tablename__ = "recall_settings"

    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), primary_key=True
    )
    reason_intervals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    category_to_reason: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    auto_suggest_on_treatment_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    auto_link_on_appointment_scheduled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Default mapping seeded into ``RecallSettings`` rows on first read.
# Upper bound of a per-reason interval, matching the settings panel's
# ``max="60"``. ``0`` means "no suggestion for this reason" (#1244).
MAX_REASON_INTERVAL_MONTHS = 60

DEFAULT_REASON_INTERVALS: dict[str, int] = {
    "hygiene": 6,
    "checkup": 12,
    "ortho_review": 1,
    "implant_review": 6,
    "post_op": 1,
    "treatment_followup": 3,
    "other": 3,
}

DEFAULT_CATEGORY_TO_REASON: dict[str, str] = {
    "preventivo": "hygiene",
    "ortodoncia": "ortho_review",
    "cirugia": "post_op",
    "implantes": "implant_review",
}
