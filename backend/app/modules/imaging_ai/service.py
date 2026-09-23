"""Business logic for the imaging_ai module."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
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
    JOB_QUEUED,
    JOB_RUNNING,
    AiJob,
)
from .runner import OcrRunner, PanoRunner, Runner, SubprocessNnunetRunner

logger = logging.getLogger(__name__)

BACKENDS: dict[str, tuple[str, str]] = {
    # backend key -> (model_id, model_version) for the audit trail.
    "nnunet": ("Dataset112_DentalSegmentator", "v100"),
    "pano": ("dental-pano-ai", "s3-weights"),
    "ocr": ("tesseract-ocr", "system"),
}


def _ocr_lang() -> str:
    return os.environ.get("DENTALPIN_TESSERACT_LANG", "eng")


def get_runner(backend: str = "nnunet") -> Runner:
    """Runner factory seam (monkeypatch in tests — never import torch here)."""
    if backend == "pano":
        app_dir = os.environ.get("DENTALPIN_PANO_APP")
        return PanoRunner(app_dir=Path(app_dir) if app_dir else None)
    if backend == "ocr":
        tesseract_bin = os.environ.get("DENTALPIN_TESSERACT_BIN")
        return OcrRunner(tesseract_bin=tesseract_bin, lang=_ocr_lang())
    return SubprocessNnunetRunner()


class AiJobService:
    @staticmethod
    async def queue_job(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        queued_by: UUID | None,
        study_id: UUID,
        document_id: UUID,
        backend: str = "nnunet",
    ) -> AiJob:
        """Queue an AI run. Patient + document must belong to the clinic
        (and to each other); anything else raises ``LookupError`` (→ 404).
        Unknown backends raise ``ValueError`` (→ 422)."""
        if backend not in BACKENDS:
            raise ValueError(f"unknown backend {backend!r} (expected one of {sorted(BACKENDS)})")
        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            raise LookupError("Patient not found")
        document = (
            await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.clinic_id == clinic_id,
                    Document.patient_id == patient_id,
                    Document.status == "active",
                )
            )
        ).scalar_one_or_none()
        if document is None:
            raise LookupError("Document not found")
        job = AiJob(
            clinic_id=clinic_id,
            patient_id=patient_id,
            study_id=study_id,
            document_id=document_id,
            backend=backend,
            model_id=BACKENDS[backend][0],
            # OCR has no weights: record the operator's tesseract language.
            model_version=_ocr_lang() if backend == "ocr" else BACKENDS[backend][1],
            queued_by=queued_by,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
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
    async def cancel_job(db: AsyncSession, job: AiJob) -> AiJob:
        """Cancel a queued job. Running jobs finish (kill comes with the
        external-worker runner); terminal states raise ``ValueError`` (→ 409)."""
        if job.status != JOB_QUEUED:
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
        """Run one queued job to a terminal state. Never raises."""
        async with async_session_maker() as db:
            job = await AiJobService.get_job(db, clinic_id, job_id)
            if job is None or job.status != JOB_QUEUED:
                return
            job.status = JOB_RUNNING
            await db.commit()

            try:
                document = (
                    await db.execute(
                        select(Document).where(
                            Document.id == job.document_id,
                            Document.clinic_id == clinic_id,
                            Document.status == "active",
                        )
                    )
                ).scalar_one_or_none()
                if document is None:
                    raise LookupError("source document gone")
                from app.modules.media.storage import get_storage_backend

                raw = await get_storage_backend().retrieve(document.storage_path)

                with tempfile.TemporaryDirectory(prefix="imaging_ai_") as tmp:
                    result = await get_runner(job.backend).run(raw, Path(tmp))

                job.log_excerpt = result.log_excerpt[:4000] or None
                if not result.ok:
                    job.status = JOB_FAILED
                    job.error = (result.error or "runner failed")[:1000]
                else:
                    artifact_ids: list[str] = []
                    for name, data in result.artifacts.items():
                        is_text = name.lower().endswith(".txt")
                        doc = await DocumentService.create_document(
                            db,
                            clinic_id,
                            job.patient_id,
                            job.queued_by,
                            data,
                            original_filename=f"ai_{job.id}_{name}",
                            mime_type="text/plain"
                            if is_text
                            else (
                                "image/png"
                                if name.lower().endswith(".png")
                                else "application/octet-stream"
                            ),
                            document_type="other",
                            title=f"AI transcript {name}" if is_text else f"AI overlay {name}",
                            media_kind="document" if is_text else "xray",
                            media_category=None if is_text else "xray",
                            tags=["ai-transcript" if is_text else "ai-overlay", job.backend],
                            paired_document_id=job.document_id,
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
                        "study_id": str(job.study_id),
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
