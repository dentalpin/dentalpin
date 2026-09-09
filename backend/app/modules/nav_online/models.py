"""nav_online models — per-clinic NAV connection + the submission queue.

Secrets (technical-user password, signature key, exchange key) are
Fernet-encrypted at rest via ``app.core.email.encryption``. Both tables
live on the module's own Alembic branch so uninstall drops them cleanly.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class NavOnlineSettings(Base, TimestampMixin):
    """Per-clinic NAV Online Számla connection (technical user + software)."""

    __tablename__ = "nav_online_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # "test" → api-test.onlineszamla.nav.gov.hu, "prod" → api.onlineszamla.nav.gov.hu
    environment: Mapped[str] = mapped_column(String(10), default="test", nullable=False)

    # The 8-digit adószám törzsszám the technical user belongs to. The
    # full 11-digit number (with VAT + county code) comes from clinics.tax_id.
    tax_number: Mapped[str | None] = mapped_column(String(11), default=None)
    technical_user_login: Mapped[str | None] = mapped_column(String(15), default=None)
    technical_user_password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    signature_key_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    exchange_key_encrypted: Mapped[str | None] = mapped_column(Text, default=None)

    # softwareId: 18 chars [0-9A-Z-], registered once per software at NAV.
    software_id: Mapped[str] = mapped_column(String(18), default="DENTALPIN-00000001")
    software_dev_contact: Mapped[str | None] = mapped_column(String(200), default=None)

    last_nav_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    next_send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_nav_online_settings_clinic", "clinic_id"),)


class NavOnlineRecord(Base):
    """One NAV data-report per issued invoice / credit note.

    State machine: ``pending`` → ``sending`` → ``sent`` (NAV accepted the
    request, ``transaction_id`` set) → ``done`` | ``rejected`` (from
    ``queryTransactionStatus``); ``failed`` on transport errors (retried
    with backoff up to ``max_attempts``), ``aborted`` when NAV aborts.
    """

    __tablename__ = "nav_online_records"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)

    operation: Mapped[str] = mapped_column(String(10), nullable=False)  # CREATE | STORNO
    invoice_number: Mapped[str] = mapped_column(String(60), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    xml_payload: Mapped[str] = mapped_column(Text, nullable=False)

    state: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    transaction_id: Mapped[str | None] = mapped_column(String(40), default=None, index=True)
    nav_status: Mapped[str | None] = mapped_column(String(20), default=None)
    error_code: Mapped[str | None] = mapped_column(String(60), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        Index("idx_nav_online_records_clinic_state", "clinic_id", "state"),
        Index("idx_nav_online_records_clinic_created", "clinic_id", "created_at"),
    )
