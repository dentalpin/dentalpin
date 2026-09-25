"""AiJob model — on-demand AI segmentation jobs over imaging studies."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

JOB_PROPOSED = "proposed"
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

REVIEW_PENDING = "pending_review"
REVIEW_CONFIRMED = "confirmed"


class AiJob(Base, TimestampMixin):
    """One on-demand AI run over a patient's DICOM bytes.

    ``document_id`` is a real FK to ``media``'s ``documents`` table, which
    is a declared dependency: the database, not just the service, now
    refuses a job pointing at a document that does not exist.
    ``series_document_ids`` holds the rest of the volume for volumetric
    backends (nnU-Net needs a DICOM series, not a single frame); it stays a
    JSONB list of ids and is validated clinic-scoped at queue time. All
    resolution is clinic-scoped; a miss fails the job, never leaks across
    tenants.

    Lifecycle: an unsupervised agent session only *proposes*
    (``queued_by`` null); a clinician's confirm moves ``proposed`` ->
    ``queued`` stamped with their id, and a supervised agent session
    queues directly (its tool call was already human-confirmed). The
    scheduler executes queued jobs. Artifacts ingest as ``document``-kind
    media rows (never gallery ``xray``) linked via
    ``artifact_document_ids`` only — no media pairing is touched — and
    stay drafts (``review_status``) until a clinician confirms them.
    Job rows are never hard-deleted (audit trail over patient data).
    """

    __tablename__ = "imaging_ai_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"))

    # Extra slices of the same series for volumetric backends
    # (nnU-Net). Empty for single-frame backends (pano).
    series_document_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Runner backend key (default "pano": the one backend that runs end
    # to end on single-frame input; "nnunet" needs a volume + weights).
    backend: Mapped[str] = mapped_column(String(40), default="pano")
    # Model id + version for audit (which weights produced this output).
    model_id: Mapped[str] = mapped_column(String(200), default="dental-pano-ai")
    model_version: Mapped[str] = mapped_column(String(40), default="s3-weights")

    # proposed | queued | running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default=JOB_QUEUED)

    # User who queued the job (artifact uploader attribution). Null only
    # while proposed: confirm stamps the confirmer before anything runs.
    queued_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, default=None
    )

    # Draft review (§4): artifacts are unconfirmed data until a clinician
    # confirms them; confirmation never rewrites the media rows.
    review_status: Mapped[str] = mapped_column(String(20), default=REVIEW_PENDING)
    confirmed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, default=None
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tail of runner stdout/stderr (bounded) + terminal error, if any.
    log_excerpt: Mapped[str | None] = mapped_column(String(4000), default=None)
    error: Mapped[str | None] = mapped_column(String(1000), default=None)

    # Media document ids of ingested draft artifacts (previews,
    # segmentations). Source linkage lives here, not in media pairing.
    artifact_document_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_imaging_ai_jobs_clinic_patient", "clinic_id", "patient_id"),
        Index("ix_imaging_ai_jobs_status", "clinic_id", "status"),
    )
