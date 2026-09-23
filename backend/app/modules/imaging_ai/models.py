"""AiJob model — on-demand AI segmentation jobs over imaging studies."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"


class AiJob(Base, TimestampMixin):
    """One on-demand AI run over a study's DICOM bytes.

    ``study_id`` / ``document_id`` are opaque UUIDs (no cross-module FKs):
    this branch must rebase onto mains where ``imaging_viewer`` may not exist
    yet. Both resolve clinic-scoped at execution time; a resolution miss
    fails the job, never leaks across tenants. Artifacts land as media
    ``Document`` rows whose ids are recorded in ``artifact_document_ids``.
    Job rows are never hard-deleted (audit trail over patient data).
    """

    __tablename__ = "imaging_ai_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    study_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))

    # Runner backend key (v1: "nnunet"). New backends slot in without callers.
    backend: Mapped[str] = mapped_column(String(40), default="nnunet")
    # Model id + version for audit (which weights produced this output).
    model_id: Mapped[str] = mapped_column(String(200), default="Dataset112_DentalSegmentator")
    model_version: Mapped[str] = mapped_column(String(40), default="v100")

    # queued | running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default=JOB_QUEUED)

    # User who queued the job (artifact uploader attribution). Nullable: the
    # agent tool path carries no authenticated identity (L25), only the HTTP
    # route attributes the requesting user.
    queued_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, default=None
    )

    # Tail of runner stdout/stderr (bounded) + terminal error, if any.
    log_excerpt: Mapped[str | None] = mapped_column(String(4000), default=None)
    error: Mapped[str | None] = mapped_column(String(1000), default=None)

    # Media document ids of ingested artifacts (previews, segmentations).
    artifact_document_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_imaging_ai_jobs_clinic_patient", "clinic_id", "patient_id"),
        Index("ix_imaging_ai_jobs_status", "clinic_id", "status"),
    )
