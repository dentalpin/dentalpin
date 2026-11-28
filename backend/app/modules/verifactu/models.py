"""Verifactu module database models.

Tables:

* ``verifactu_settings`` — per-clinic configuration (one row per clinic).
* ``verifactu_certificates`` — uploaded PFX/P12 certificates (encrypted).
* ``verifactu_records`` — append-only fiscal ledger of every register
  (alta or anulacion) sent to AEAT, with current XML payload, hash chain,
  and last AEAT response.
* ``verifactu_record_attempts`` — historical snapshots of every XML
  payload + huella generated for a record. Required by RD 1007/2023
  art. 8 (trazabilidad de todos los registros generados, incluso
  los rechazados antes de subsanación).
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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User
    from app.modules.billing.models import Invoice


ENVIRONMENTS = ("test", "prod")
RECORD_TYPES = ("alta", "anulacion")
RECORD_STATES = (
    "pending",
    "sending",
    "accepted",
    "accepted_with_errors",
    "rejected",
    "failed_transient",
    "failed_validation",
)
TIPO_FACTURA = ("F1", "F2", "F3", "R1", "R2", "R3", "R4", "R5")


class VerifactuSettings(Base, TimestampMixin):
    """Per-clinic Verifactu configuration. Exactly one row per clinic."""

    __tablename__ = "verifactu_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), unique=True, index=True
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    environment: Mapped[str] = mapped_column(String(10), default="test", nullable=False)

    numero_instalacion: Mapped[str] = mapped_column(String(60), nullable=False)

    last_huella: Mapped[str | None] = mapped_column(String(64), default=None)
    last_record_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    next_send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_aeat_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # SIF producer identity. Goes into <SistemaInformatico> on every
    # record. Defaults can come from env vars but the canonical source
    # is whatever the wizard wrote here.
    producer_nif: Mapped[str | None] = mapped_column(String(20), default=None)
    producer_name: Mapped[str | None] = mapped_column(String(200), default=None)
    producer_id_sistema: Mapped[str] = mapped_column(String(2), default="DP", nullable=False)
    producer_version: Mapped[str | None] = mapped_column(String(20), default=None)
    declaracion_responsable_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    declaracion_responsable_signed_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), default=None
    )

    # Set by tasks._notify_rejected when an admin email is sent. Used
    # to throttle to one alert per clinic per 30 min — avoids flooding
    # admins when a systemic issue (bad NIF on the clinic, expired cert)
    # triggers many rejections in a single batch.
    last_rejected_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    clinic: Mapped["Clinic"] = relationship()


class VerifactuVatClassification(Base, TimestampMixin):
    """Per-clinic AEAT classification override for a catalog VAT type.

    Verifactu needs a Spain-specific classification for each VAT line
    (S1, S2, E1..E6, N1, N2). The catalog ``vat_types`` table stays
    country-agnostic — only ``rate`` and label. This table lets the
    clinic admin pin the AEAT classification per VAT type from the
    Verifactu config panel.

    When no row exists for a given ``vat_type_id``, the runtime falls
    back to ``services.iva_classifier.classify`` heuristics.
    """

    __tablename__ = "verifactu_vat_classifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), index=True
    )
    vat_type_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vat_types.id", ondelete="CASCADE"), index=True
    )

    # AEAT CalificacionOperacion / OperacionExenta value. One of:
    #   S1 / S2 — sujeto, no exento
    #   E1..E6  — exento (con causa)
    #   N1 / N2 — no sujeta
    classification: Mapped[str] = mapped_column(String(2), nullable=False)
    # When ``classification`` starts with ``E`` we also store the cause
    # explicitly (E1..E6) so the XML emitter can populate
    # ``OperacionExenta`` directly. Redundant for non-exempt rows.
    exemption_cause: Mapped[str | None] = mapped_column(String(2), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (
        UniqueConstraint("clinic_id", "vat_type_id", name="uq_verifactu_vat_class_clinic_vat"),
    )


class VerifactuCertificate(Base, TimestampMixin):
    """Uploaded PFX/P12 certificate for a clinic.

    Only one ``is_active=True`` per clinic at a time (enforced by partial
    unique index in migration). Older certificates are kept for audit.
    """

    __tablename__ = "verifactu_certificates"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), index=True
    )

    pfx_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    subject_cn: Mapped[str | None] = mapped_column(String(200), default=None)
    issuer_cn: Mapped[str | None] = mapped_column(String(200), default=None)
    nif_titular: Mapped[str | None] = mapped_column(String(20), default=None)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Set by the daily cert-expiry job whenever it sends an alert email.
    # Used to throttle to one alert per certificate per daily run (20 h window) regardless
    # of how many admins receive it.
    last_expiry_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    uploaded_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    clinic: Mapped["Clinic"] = relationship()
    uploader: Mapped["User | None"] = relationship()


class VerifactuRecord(Base):
    """Append-only ledger of registers submitted to AEAT.

    No ``TimestampMixin`` because we only want a single ``created_at``
    field; the canonical timestamp is ``aeat_timestamp_presentacion`` once
    AEAT accepts the record. The XML payload is stored verbatim — legal
    requirement for audit trail and chain reconstruction.
    """

    __tablename__ = "verifactu_records"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="RESTRICT"), index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), index=True
    )

    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_factura: Mapped[str] = mapped_column(String(2), nullable=False)
    tipo_rectificativa: Mapped[str | None] = mapped_column(String(1), default=None)

    serie_numero: Mapped[str] = mapped_column(String(60), nullable=False)
    fecha_expedicion: Mapped[date] = mapped_column(Date, nullable=False)
    cuota_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    importe_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    huella: Mapped[str] = mapped_column(String(64), nullable=False)
    huella_anterior: Mapped[str | None] = mapped_column(String(64), default=None)
    is_first_record: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fecha_hora_huso_gen_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    xml_payload: Mapped[str | None] = mapped_column(Text, default=None)
    state: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)

    aeat_csv: Mapped[str | None] = mapped_column(String(60), default=None)
    aeat_estado_envio: Mapped[str | None] = mapped_column(String(30), default=None)
    aeat_estado_registro: Mapped[str | None] = mapped_column(String(30), default=None)
    aeat_codigo_error: Mapped[int | None] = mapped_column(Integer, default=None)
    aeat_descripcion_error: Mapped[str | None] = mapped_column(Text, default=None)
    aeat_timestamp_presentacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    aeat_response_xml: Mapped[str | None] = mapped_column(Text, default=None)

    subsanacion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rechazo_previo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submission_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    extra: Mapped[dict | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None, nullable=False, default=lambda: datetime.now()
    )

    clinic: Mapped["Clinic"] = relationship()
    invoice: Mapped["Invoice"] = relationship()

    __table_args__ = (
        UniqueConstraint("clinic_id", "huella", name="uq_verifactu_record_clinic_huella"),
        Index("ix_verifactu_records_clinic_created", "clinic_id", "created_at"),
        Index("ix_verifactu_records_clinic_state", "clinic_id", "state"),
    )


class VerifactuRecordAttempt(Base):
    """Historical snapshot of one XML payload + huella sent for a record.

    A record is regenerated (Subsanación con datos corregidos) by
    overwriting ``VerifactuRecord.xml_payload`` and ``huella``. RD
    1007/2023 art. 8 requires conservar la trazabilidad de todos los
    registros generados — including the rejected XML before subsanación.
    Each call to ``regenerate_record`` snapshots the previous state here
    before mutating the parent record.
    """

    __tablename__ = "verifactu_record_attempts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    record_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verifactu_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)

    xml_payload: Mapped[str] = mapped_column(Text, nullable=False)
    huella: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)

    aeat_codigo_error: Mapped[int | None] = mapped_column(Integer, default=None)
    aeat_descripcion_error: Mapped[str | None] = mapped_column(Text, default=None)
    aeat_response_xml: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now()
    )

    __table_args__ = (
        UniqueConstraint("record_id", "attempt_no", name="uq_verifactu_attempt_record_no"),
    )
