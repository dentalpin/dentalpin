"""sistema_ts models — per-clinic Sistema TS credentials, the document
queue, per-patient opposition, per-catalog-item expense type.

Everything lives on the module's own Alembic branch (``sistema_ts``);
nothing is added to ``billing``, ``patients`` or ``catalog`` (ADR 0026).
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class SistemaTsSettings(Base, TimestampMixin):
    """Per-clinic Sistema TS access (spec §4.1: basic auth + encrypted pincode)."""

    __tablename__ = "sistema_ts_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # "test" → invioSS730pTest.sanita.finanze.it, "prod" → invioSS730p.sanita.finanze.it
    environment: Mapped[str] = mapped_column(String(10), default="test", nullable=False)

    # Sistema TS credentials of the sender (username = the sender's codice
    # fiscale as registered on sistemats.it). Password and pincode are
    # Fernet-encrypted at rest; the pincode is additionally RSA-encrypted
    # with the Sistema TS certificate on every request.
    username: Mapped[str | None] = mapped_column(String(16), default=None)
    password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    pincode_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    # Optional replacement for the vendored SanitelCF certificate (PEM/DER,
    # base64 text) — the portal regenerates it periodically.
    certificate_b64: Mapped[str | None] = mapped_column(Text, default=None)

    # Proprietario: the professional's codice fiscale (or the structure's
    # owner). codice_regione / asl / ssa only for structures.
    cf_proprietario: Mapped[str | None] = mapped_column(String(16), default=None)
    codice_regione: Mapped[str | None] = mapped_column(String(3), default=None)
    codice_asl: Mapped[str | None] = mapped_column(String(3), default=None)
    codice_ssa: Mapped[str | None] = mapped_column(String(10), default=None)
    # numDocumentoFiscale.dispositivo — "1" for invoices (spec table 2)
    dispositivo: Mapped[str] = mapped_column(String(10), default="1", nullable=False)
    default_tipo_spesa: Mapped[str] = mapped_column(String(2), default="SR", nullable=False)
    # Invoices issued before this date are not picked up (module enabled mid-year)
    sync_from: Mapped[date | None] = mapped_column(Date, default=None)

    last_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    next_send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])


class SistemaTsDocument(Base):
    """One Sistema TS operation per fiscal document.

    ``operation``: ``inserimento`` | ``variazione`` | ``cancellazione`` |
    ``rimborso``. State: ``pending`` → ``sending`` → ``accepted`` |
    ``accepted_with_warnings`` (esito 0/2, ``protocollo`` set) |
    ``rejected`` (esito 1, blocking messages) | ``failed`` (transport,
    after max attempts). The request/response XML are the proof kept for
    ten years (ADR 0026 §6); codici fiscali inside them are encrypted as
    sent.
    """

    __tablename__ = "sistema_ts_documents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)

    operation: Mapped[str] = mapped_column(String(14), nullable=False)
    # Fiscal document identity as sent (pIva, dataEmissione, dispositivo, numDocumento)
    p_iva: Mapped[str] = mapped_column(String(11), nullable=False)
    data_emissione: Mapped[date] = mapped_column(Date, nullable=False)
    dispositivo: Mapped[str] = mapped_column(String(10), nullable=False)
    num_documento: Mapped[str] = mapped_column(String(60), nullable=False)
    data_pagamento: Mapped[date | None] = mapped_column(Date, default=None)
    tipo_documento: Mapped[str] = mapped_column(String(1), default="F", nullable=False)
    pagamento_tracciato: Mapped[str] = mapped_column(String(2), default="SI", nullable=False)
    flag_opposizione: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # [{"tipo_spesa": "SR", "flag_tipo_spesa": null, "importo": "30.00", "aliquota_iva": null, "natura_iva": "N4"}]
    voci: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # For rimborso/variazione/cancellazione: the accepted document this refers to
    refers_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sistema_ts_documents.id"), default=None
    )

    state: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    request_xml: Mapped[str | None] = mapped_column(Text, default=None)
    response_xml: Mapped[str | None] = mapped_column(Text, default=None)
    esito: Mapped[int | None] = mapped_column(Integer, default=None)
    protocollo: Mapped[str | None] = mapped_column(String(20), default=None, index=True)
    messages: Mapped[list | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    environment: Mapped[str | None] = mapped_column(String(10), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        Index("idx_sistema_ts_documents_clinic_state", "clinic_id", "state"),
        Index("idx_sistema_ts_documents_clinic_created", "clinic_id", "created_at"),
        Index("idx_sistema_ts_documents_invoice_op", "invoice_id", "operation"),
    )


class SistemaTsPatientOpposition(Base, TimestampMixin):
    """The patient's opposition to sending their expenses to the Agenzia
    delle Entrate (spec table 5: documents still go, with flagOpposizione=1
    and without cfCittadino). One row per patient; ``revoked_at`` set when
    the patient withdraws it."""

    __tablename__ = "sistema_ts_patient_opposition"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    opposed_since: Mapped[date] = mapped_column(Date, nullable=False)
    revoked_at: Mapped[date | None] = mapped_column(Date, default=None)
    recorded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    note: Mapped[str | None] = mapped_column(String(300), default=None)

    __table_args__ = (
        UniqueConstraint("clinic_id", "patient_id", name="uq_sistema_ts_opposition_patient"),
    )


class SistemaTsItemType(Base, TimestampMixin):
    """``tipoSpesa`` per catalog item (ADR 0026 §2); items without a row use
    the clinic default (``SR``)."""

    __tablename__ = "sistema_ts_item_types"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    catalog_item_id: Mapped[UUID] = mapped_column(ForeignKey("treatment_catalog_items.id"))
    tipo_spesa: Mapped[str] = mapped_column(String(2), nullable=False)
    flag_tipo_spesa: Mapped[str | None] = mapped_column(String(1), default=None)

    __table_args__ = (
        UniqueConstraint("clinic_id", "catalog_item_id", name="uq_sistema_ts_item_type"),
    )
