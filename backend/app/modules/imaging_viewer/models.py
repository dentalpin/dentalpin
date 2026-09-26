"""ImagingStudy model — DICOM study index on top of media documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class ImagingStudy(Base, TimestampMixin):
    """Index row for one DICOM study viewable in the embedded viewer.

    The pixel data stays in the referenced media ``Document`` (storage path);
    this row carries identity (StudyInstanceUID), classification, and the
    extracted DICOM tags so listings never parse files.
    """

    __tablename__ = "imaging_studies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), index=True)

    study_uid: Mapped[str] = mapped_column(String(128))
    modality: Mapped[str | None] = mapped_column(String(16), default=None)
    study_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Extracted DICOM tags (Study Date, Modality, Body Part, rows/columns…).
    dicom_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # active | archived (soft-delete: patient data is never hard-deleted).
    status: Mapped[str] = mapped_column(String(20), default="active")

    __table_args__ = (
        Index("ix_imaging_studies_clinic_patient", "clinic_id", "patient_id"),
        Index("ix_imaging_studies_study_uid", "clinic_id", "study_uid"),
        # Idempotent indexing: one ACTIVE row per document (a shared
        # StudyInstanceUID across RVG frames must never duplicate rows).
        # Partial so archived rows keep their history; index_core
        # pre-checks the active row first (pay_0005 precedent).
        Index(
            "uq_imaging_studies_clinic_document",
            "clinic_id",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class RvgLink(Base, TimestampMixin):
    """Approved DICOM-identity → patient binding for RVG auto-import.

    Once a human approves one file carrying a DICOM ``patient_id`` value,
    later files with the same value import without review. ``created_by``
    attributes those auto-imports to the approving user (scheduler ticks
    have no actor of their own).
    """

    __tablename__ = "imaging_rvg_links"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    dicom_patient_id: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        Index("ix_imaging_rvg_links_clinic_dicom", "clinic_id", "dicom_patient_id", unique=True),
    )


class RvgImport(Base, TimestampMixin):
    """One scanned RVG file and its journey through the approval queue.

    ``status``: pending | approved | rejected | failed. Failed rows keep
    their ``error`` visible so broken files stay discoverable and retryable;
    decided rows keep their ``study_id``/``document_id`` for audit.
    """

    __tablename__ = "imaging_rvg_imports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"), default=None)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), default=None)
    study_id: Mapped[UUID | None] = mapped_column(ForeignKey("imaging_studies.id"), default=None)

    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    identity_tags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    suggested_patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"), default=None
    )
    match_score: Mapped[int | None] = mapped_column(default=None)
    match_reason: Mapped[str | None] = mapped_column(String(255), default=None)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(String(500), default=None)

    __table_args__ = (
        Index("ix_imaging_rvg_imports_clinic_hash", "clinic_id", "content_hash", unique=True),
        Index("ix_imaging_rvg_imports_clinic_status", "clinic_id", "status"),
    )


class ImagingAnnotation(Base, TimestampMixin):
    """Human annotation overlay on a study (ruler / freehand / note).

    Coordinates are normalized 0-1 relative to the frame so overlays survive
    resizes; ``spacing_mm`` records the pixel spacing used for a ruler mm
    value (null when the study carries no spacing — then mm is absent, never
    guessed). Originals stay immutable; deleting archives (L7).
    """

    __tablename__ = "imaging_annotations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    study_id: Mapped[UUID] = mapped_column(ForeignKey("imaging_studies.id"), index=True)

    kind: Mapped[str] = mapped_column(String(20))  # ruler | freehand | note
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    spacing_mm: Mapped[float | None] = mapped_column(default=None)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # active | archived (soft-delete: patient-linked rows are never hard-deleted).
    status: Mapped[str] = mapped_column(String(20), default="active")

    __table_args__ = (Index("ix_imaging_annotations_study", "clinic_id", "study_id", "status"),)
