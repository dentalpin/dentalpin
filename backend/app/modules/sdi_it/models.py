"""sdi_it models — per-clinic SDI settings + the per-invoice record queue.

Both tables live on the module's own Alembic branch (``sdi_it``) so
uninstall drops them cleanly; nothing is added to ``billing``.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class SdiItSettings(Base, TimestampMixin):
    """Per-clinic FatturaPA/SDI configuration."""

    __tablename__ = "sdi_it_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # "manual": the admin downloads the XML, uploads it (portal / PEC client)
    # and imports the receipt. "pec" (later PR) automates both legs.
    transport: Mapped[str] = mapped_column(String(10), default="manual", nullable=False)
    regime_fiscale: Mapped[str] = mapped_column(String(4), default="RF01", nullable=False)
    bollo_virtuale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    riferimento_normativo: Mapped[str] = mapped_column(
        String(100), default="Esente IVA art. 10 n. 18 DPR 633/72", nullable=False
    )
    # ProgressivoInvio counter — unique per transmitter, base-36 rendered.
    progressivo_invio: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_receipt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

    # PEC transport (transport == "pec"): the clinic's own PEC mailbox sends
    # the file to the SDI and receives the receipts. Passwords are Fernet-
    # encrypted at rest (app.core.email.encryption). ``sdi_pec_address`` is
    # the SDI mailbox: the first message goes to sdi01@pec.fatturapa.it and
    # the SDI answers from the dedicated address it assigns (spec §1.3),
    # which the poller stores here.
    pec_address: Mapped[str | None] = mapped_column(String(255), default=None)
    sdi_pec_address: Mapped[str] = mapped_column(
        String(255), default="sdi01@pec.fatturapa.it", nullable=False
    )
    smtp_host: Mapped[str | None] = mapped_column(String(255), default=None)
    smtp_port: Mapped[int] = mapped_column(Integer, default=465, nullable=False)
    smtp_username: Mapped[str | None] = mapped_column(String(255), default=None)
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    imap_host: Mapped[str | None] = mapped_column(String(255), default=None)
    imap_port: Mapped[int] = mapped_column(Integer, default=993, nullable=False)
    imap_folder: Mapped[str] = mapped_column(String(100), default="INBOX", nullable=False)
    last_pec_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    next_send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])


class SdiItRecord(Base):
    """One FPR12 file per issued B2B invoice / credit note.

    State machine (ADR 0025 §4): ``pending`` (built, not yet handed to the
    SDI) → ``exported`` (downloaded, or sent through PEC; awaiting a receipt) →
    ``delivered`` (RC) | ``undeliverable`` (MC, action: notify recipient)
    | ``rejected`` (NS, action: fix and requeue with the same number).
    """

    __tablename__ = "sdi_it_records"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)

    tipo_documento: Mapped[str] = mapped_column(String(4), nullable=False)  # TD01 | TD04
    invoice_number: Mapped[str] = mapped_column(String(60), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(200), default=None)
    recipient_tax_id: Mapped[str | None] = mapped_column(String(20), default=None)
    codice_destinatario: Mapped[str] = mapped_column(String(7), nullable=False)

    progressivo: Mapped[str] = mapped_column(String(10), nullable=False)
    file_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    xml_payload: Mapped[str] = mapped_column(Text, nullable=False)

    state: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # How the file reached the SDI: "manual" (download/upload) or "pec".
    transport: Mapped[str | None] = mapped_column(String(10), default=None)
    message_id: Mapped[str | None] = mapped_column(String(255), default=None)

    sdi_identifier: Mapped[str | None] = mapped_column(String(40), default=None, index=True)
    receipt_type: Mapped[str | None] = mapped_column(String(4), default=None)
    receipt_xml: Mapped[str | None] = mapped_column(Text, default=None)
    receipt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_code: Mapped[str | None] = mapped_column(String(60), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        Index("idx_sdi_it_records_clinic_state", "clinic_id", "state"),
        Index("idx_sdi_it_records_clinic_created", "clinic_id", "created_at"),
    )
