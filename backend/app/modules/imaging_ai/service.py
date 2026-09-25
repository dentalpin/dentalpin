"""Business logic for the imaging_ai module."""

from __future__ import annotations

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.database import async_session_maker
from app.modules.media.models import Document
from app.modules.media.service import DocumentService
from app.modules.patients.models import Patient

from .models import (
    JOB_CANCELLED,
    JOB_DONE,
    JOB_FAILED,
    JOB_PROPOSED,
    JOB_QUEUED,
    JOB_RUNNING,
    REVIEW_CONFIRMED,
    REVIEW_PENDING,
    AiJob,
)
from .runner import PanoRunner, Runner, SubprocessNnunetRunner, nnunet_env, pano_env
from .volume import VolumeError, dicom_series_to_nifti

logger = logging.getLogger(__name__)

BACKENDS: dict[str, tuple[str, str]] = {
    # backend key -> (model_id, model_version) for the audit trail.
    # pano is the default: the one backend that runs end to end on
    # single-frame input. nnunet needs a series + operator weights.
    "pano": ("dental-pano-ai", "s3-weights"),
    "nnunet": ("Dataset112_DentalSegmentator", "v100"),
}

MIN_NNUNET_SLICES = 2


def get_runner(backend: str = "pano") -> Runner:
    """Runner factory seam (monkeypatch in tests — never import torch here)."""
    if backend == "pano":
        app_dir, python_exe = pano_env()
        return PanoRunner(app_dir=app_dir, python_exe=python_exe)
    if backend == "nnunet":
        weights_dir, allow_cpu = nnunet_env()
        return SubprocessNnunetRunner(weights_dir=weights_dir, allow_cpu=allow_cpu)
    raise ValueError(f"unknown backend {backend!r} (expected one of {sorted(BACKENDS)})")


class AiJobService:
    @staticmethod
    async def queue_job(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        queued_by: UUID | None,
        document_id: UUID,
        series_document_ids: list[UUID] | None = None,
        backend: str = "pano",
    ) -> AiJob:
        """Queue an AI run — or propose one when ``queued_by`` is null.

        Patient + documents must belong to the clinic (and to each
        other); anything else raises ``LookupError`` (→ 404). Unknown
        backends raise ``ValueError`` (→ 422). ``nnunet`` needs a volume:
        at least ``MIN_NNUNET_SLICES`` slices of one series, else
        ``ValueError`` with an actionable message. A null ``queued_by``
        (agent path, no authenticated identity) creates a ``proposed``
        job: nothing executes until a clinician confirms it, and the
        confirm stamps the attributor — so ``uploaded_by`` (NOT NULL)
        always resolves at artifact time.
        """
        if backend not in BACKENDS:
            raise ValueError(f"unknown backend {backend!r} (expected one of {sorted(BACKENDS)})")
        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            raise LookupError("Patient not found")
        series_ids = list(dict.fromkeys(series_document_ids or []))
        wanted = [document_id, *[i for i in series_ids if i != document_id]]
        documents = (
            (
                await db.execute(
                    select(Document).where(
                        Document.id.in_(wanted),
                        Document.clinic_id == clinic_id,
                        Document.patient_id == patient_id,
                        Document.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        found = {d.id for d in documents}
        if document_id not in found:
            raise LookupError("Document not found")
        if backend == "nnunet":
            missing = [i for i in series_ids if i not in found]
            if missing:
                raise LookupError("Series document not found")
            if len(wanted) < MIN_NNUNET_SLICES:
                raise ValueError(
                    f"nnunet needs a volume: queue at least {MIN_NNUNET_SLICES} slices "
                    "of one series (or use the pano backend for single frames)"
                )
        job = AiJob(
            clinic_id=clinic_id,
            patient_id=patient_id,
            document_id=document_id,
            series_document_ids=[str(i) for i in series_ids],
            backend=backend,
            model_id=BACKENDS[backend][0],
            model_version=BACKENDS[backend][1],
            status=JOB_QUEUED if queued_by is not None else JOB_PROPOSED,
            queued_by=queued_by,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def confirm_job(db: AsyncSession, job: AiJob, user_id: UUID) -> AiJob:
        """Clinician confirm — the single review gate (§4 + attribution).

        ``proposed`` -> ``queued`` stamped with the confirmer (authorizes
        the run and fixes artifact attribution); ``done`` +
        ``pending_review`` -> ``confirmed`` (records the draft review).
        Anything else raises ``ValueError`` (→ 409).
        """
        if job.status == JOB_PROPOSED:
            job.status = JOB_QUEUED
            job.queued_by = user_id
        elif job.status == JOB_DONE and job.review_status == REVIEW_PENDING:
            job.review_status = REVIEW_CONFIRMED
            job.confirmed_by = user_id
            job.confirmed_at = datetime.now(UTC)
        else:
            raise ValueError(f"cannot confirm job in status {job.status}/{job.review_status}")
        await db.commit()
        await db.refresh(job)
        if job.review_status == REVIEW_CONFIRMED:
            await event_bus.publish(
                EventType.IMAGING_AI_JOB_CONFIRMED,
                {
                    "job_id": str(job.id),
                    "clinic_id": str(job.clinic_id),
                    "patient_id": str(job.patient_id),
                    "confirmed_by": str(user_id),
                },
            )
        return job

    @staticmethod
    async def get_job(db: AsyncSession, clinic_id: UUID, job_id: UUID) -> AiJob | None:
        """Fetch one job, clinic-scoped. Finished rows stay fetchable (audit)."""
        return (
            await db.execute(select(AiJob).where(AiJob.id == job_id, AiJob.clinic_id == clinic_id))
        ).scalar_one_or_none()

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AiJob], int]:
        """List jobs with multi-tenancy and pagination."""
        stmt = select(AiJob).where(AiJob.clinic_id == clinic_id)
        if patient_id is not None:
            stmt = stmt.where(AiJob.patient_id == patient_id)
        stmt = stmt.order_by(AiJob.created_at.desc())
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        page_size = min(max(page_size, 1), 100)
        offset = (max(page, 1) - 1) * page_size
        items = list((await db.execute(stmt.offset(offset).limit(page_size))).scalars().all())
        return items, total

    @staticmethod
    async def list_dicom_documents(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[Document]:
        """DICOM candidates for the series picker (clinic + patient scoped).

        The DICOM predicate lives in SQL, not in the router: loading every
        document of the patient and filtering by mime/extension afterwards
        meant a patient with a full gallery shipped rows the picker can
        never show. The declared DICOM mime and a ``.dcm`` filename are both
        matched, so an octet-stream upload the media layer accepts as
        sniffed DICOM still appears.
        """
        stmt = select(Document).where(
            Document.clinic_id == clinic_id,
            Document.patient_id == patient_id,
            Document.status == "active",
            or_(
                Document.mime_type == "application/dicom",
                func.lower(Document.original_filename).like("%.dcm"),
            ),
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def cancel_job(db: AsyncSession, job: AiJob) -> AiJob:
        """Cancel a proposed or queued job. Running jobs finish (kill comes
        with the external-worker runner); terminal states raise
        ``ValueError`` (→ 409)."""
        if job.status not in (JOB_PROPOSED, JOB_QUEUED):
            raise ValueError(f"cannot cancel job in status {job.status}")
        job.status = JOB_CANCELLED
        await db.commit()
        await db.refresh(job)
        return job

    # ------------------------------------------------------------------
    # Background execution (own session — never the request's).
    # ------------------------------------------------------------------

    @staticmethod
    async def execute_in_background(job_id: UUID, clinic_id: UUID) -> None:
        """Run one queued job to a terminal state. Never raises.

        The row lock means a concurrent scheduler tick blocks here and
        then sees a non-queued row — only one executor wins the race
        (migration_import pattern).
        """
        async with async_session_maker() as db:
            result = await db.execute(select(AiJob).where(AiJob.id == job_id).with_for_update())
            job = result.scalar_one_or_none()
            if job is None or job.clinic_id != clinic_id or job.status != JOB_QUEUED:
                return
            if job.queued_by is None:
                job.status = JOB_FAILED
                job.error = "job reached execution without attribution (confirm first)"
                await db.commit()
                return
            job.status = JOB_RUNNING
            await db.commit()

            try:
                runner_input = await AiJobService._build_runner_input(db, clinic_id, job)

                with tempfile.TemporaryDirectory(prefix="imaging_ai_") as tmp:
                    result = await get_runner(job.backend).run(runner_input, Path(tmp))

                job.log_excerpt = result.log_excerpt[:4000] or None
                if not result.ok:
                    job.status = JOB_FAILED
                    job.error = (result.error or "runner failed")[:1000]
                else:
                    artifact_ids: list[str] = []
                    for name, data in result.artifacts.items():
                        lowered = name.lower()
                        is_text = lowered.endswith(".txt")
                        # dental-pano-ai's per-FDI findings table is CSV, and
                        # is the clinically useful output of a run: it is
                        # ingested as a text draft so a clinician can open
                        # it during review. Kept as text/plain (not
                        # text/csv) because that is the module's existing
                        # text-artifact mime.
                        is_csv = lowered.endswith(".csv")
                        is_jpeg = lowered.endswith((".jpg", ".jpeg"))
                        if is_text or is_csv:
                            mime_type = "text/plain"
                        elif lowered.endswith(".png"):
                            mime_type = "image/png"
                        elif is_jpeg:
                            mime_type = "image/jpeg"
                        else:
                            mime_type = "application/octet-stream"
                        # Drafts, never records (§4): kind ``document`` keeps
                        # artifacts out of the photo/xray gallery rail and
                        # fires no photo event; source linkage lives on the
                        # job row — media pairing is never touched.
                        doc = await DocumentService.create_document(
                            db,
                            clinic_id,
                            job.patient_id,
                            job.queued_by,
                            data,
                            original_filename=f"ai_{job.id}_{name.rsplit('/', 1)[-1]}",
                            mime_type=mime_type,
                            document_type="other",
                            title=f"AI draft findings {name.rsplit('/', 1)[-1]}"
                            if is_csv
                            else f"AI draft transcript {name.rsplit('/', 1)[-1]}"
                            if is_text
                            else f"AI draft overlay {name.rsplit('/', 1)[-1]}",
                            media_kind="document",
                            media_category=None,
                            tags=[
                                "ai-draft",
                                "ai-findings"
                                if is_csv
                                else "ai-transcript"
                                if is_text
                                else "ai-overlay",
                                job.backend,
                            ],
                        )
                        artifact_ids.append(str(doc.id))
                    job.artifact_document_ids = artifact_ids
                    job.status = JOB_DONE
                await db.commit()
                await event_bus.publish(
                    EventType.IMAGING_AI_JOB_DONE,
                    {
                        "job_id": str(job.id),
                        "clinic_id": str(clinic_id),
                        "patient_id": str(job.patient_id),
                        "status": job.status,
                    },
                )
            except Exception as exc:  # noqa: BLE001 — jobs always land terminal
                logger.exception("imaging_ai.execute_in_background failed")
                try:
                    async with async_session_maker() as fail_db:
                        fail_job = await AiJobService.get_job(fail_db, clinic_id, job_id)
                        if fail_job is not None and fail_job.status == JOB_RUNNING:
                            fail_job.status = JOB_FAILED
                            fail_job.error = str(exc)[:1000]
                            await fail_db.commit()
                except Exception:  # noqa: BLE001 — last-resort guard
                    logger.exception("imaging_ai failure bookkeeping failed")

    @staticmethod
    async def _build_runner_input(db: AsyncSession, clinic_id: UUID, job: AiJob) -> bytes:
        """Fetch + shape the runner input (single frame, or stacked volume)."""
        from app.modules.media.storage import get_storage_backend

        wanted = [job.document_id, *[UUID(i) for i in (job.series_document_ids or [])]]
        documents = (
            (
                await db.execute(
                    select(Document).where(
                        Document.id.in_(wanted),
                        Document.clinic_id == clinic_id,
                        Document.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        by_id = {d.id: d for d in documents}
        missing = [str(i) for i in wanted if i not in by_id]
        if missing:
            raise LookupError(f"source documents gone: {missing}")
        storage = get_storage_backend()
        blobs = [await storage.retrieve(by_id[i].storage_path) for i in wanted]
        if job.backend == "nnunet":
            try:
                return dicom_series_to_nifti(blobs).data
            except VolumeError as exc:
                raise LookupError(str(exc)) from exc
        return blobs[0]
