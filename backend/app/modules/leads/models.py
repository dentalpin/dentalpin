"""leads — inbound enquiries from an external website/form.

Three tables:

* ``leads`` — one row per enquiry that did **not** match an existing
  patient. A matched enquiry never writes here: it becomes a recall in
  the ``recalls`` module instead (the routing rule lives in
  ``service.LeadIntakeService.route``).
* ``leads_intake_keys`` — exactly one intake key per clinic (the
  ``X-Lead-Key`` the clinic's website sends). Only the SHA-256 hash is
  stored; the plaintext is returned once from ``/settings/intake-key/rotate``.
* ``leads_settings`` — exactly one row per clinic: the daily intake cap
  and today's counter (clinic data, edited at Settings → Integrations →
  *Formulario web*, never an env var).

Cross-module FKs are limited to ``clinics.id`` (core) and ``patients.id``
(declared in ``manifest.depends``). Nothing links to ``recalls``: a
matched enquiry's record is the recall itself, deduped inside the
recalls module on ``(patient, reason)``.
"""

from __future__ import annotations

from datetime import date, datetime
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

# Status values are documented here, not enforced at the DB level (same
# convention as ``Patient.status`` / ``Recall.status``).
#
#   new        — received, nobody has called yet
#   contacted  — the front desk reached out
#   converted  — became a patient (``patient_id`` / ``converted_at`` set)
#   discarded  — the only removal path; leads are never hard-deleted
LEAD_STATUSES = ("new", "contacted", "converted", "discarded")

#: Week days an enquiry can name, in display order (ISO-8601 starts Monday).
#: Stored as these codes; the UI renders localized weekday names.
AVAILABILITY_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

#: Optional preference inside the chosen days. Absent means "any time".
AVAILABILITY_SLOTS = ("morning", "afternoon", "evening")


def canonical_days(days: list[str] | None) -> list[str] | None:
    """Deduplicate and order days mon..sun; unknown codes are dropped.

    The API validates the codes, so dropping here is a belt-and-braces for
    rows written before a code was retired — an unexpected value must never
    end up in the week strip the front desk reads.
    """
    if not days:
        return None
    seen = {day for day in days if day in AVAILABILITY_DAYS}
    return [day for day in AVAILABILITY_DAYS if day in seen] or None


class Lead(Base, TimestampMixin):
    """A genuinely new enquiry, until it is converted or discarded."""

    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )

    # The external form collects a single name field.
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    motive: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # When the person can be reached. Structured on purpose: the front desk
    # reads it as a week strip and the card shows at a glance which days are
    # open, which free text ("weekday afternoons") cannot do. Days are
    # canonicalised (mon..sun, no duplicates) by the service.
    availability_days: Mapped[list[str] | None] = mapped_column(JSONB)
    # Optional preference inside the day ("morning" | "afternoon" | "evening").
    # NULL means "no preference", not "unknown".
    availability_slot: Mapped[str | None] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")

    # Set on conversion. SET NULL (not CASCADE): deleting a patient chart
    # must not delete the marketing history of the enquiry.
    patient_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # The list page's default query shape: filter by status, sort by
        # created_at, always scoped to one clinic.
        Index("ix_leads_clinic_status_created", "clinic_id", "status", "created_at"),
    )


class LeadIntakeKey(Base, TimestampMixin):
    """The clinic's single intake key (hashed). One row per clinic."""

    __tablename__ = "leads_intake_keys"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )

    # SHA-256 hex of the ``lk_…`` plaintext — same reasoning as
    # ``integrations.ApiToken.token_hash``: a leaked DB dump must not
    # hand out working keys.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # e.g. ``lk_AbC12xYz`` — shown in the UI so a clinic can tell keys
    # apart after a rotation, without ever revealing the secret.
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    # Soft revoke: the operator's kill switch, no deploy required.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("clinic_id", name="uq_leads_intake_keys_clinic"),)


class LeadSettings(Base):
    """Per-clinic intake configuration + today's volume counter.

    Lazy-created on first read by ``LeadSettingsService.get_or_create``.
    The counter lives here (not on the key row) so the cap and the count
    are read and bumped in one atomic statement, and so the settings page
    works before any key exists. Rotating the key must NOT reset it.
    """

    __tablename__ = "leads_settings"

    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), primary_key=True
    )
    # 0 = unlimited. The column default IS the default — there is no env
    # var (two sources of truth guarantee a support call).
    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, server_default="200")
    # Attempts accepted today, including matched (recall) ones — the
    # flood gauge. Counted before the write, so blocked attempts stay
    # visible instead of only showing that intake stopped.
    day_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    day_count_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
