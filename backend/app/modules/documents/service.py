"""Business logic for the documents module.

All functions are stateless static methods on ``DocumentService``.
Every query filters by ``clinic_id`` (multi-tenancy, mandatory).
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.patients.service import PatientService

from .models import DocumentStatus, GeneratedDocument
from .pdf import DocumentPDFService


def _documents_root() -> Path:
    """Filesystem root where rendered PDFs are persisted.

    Defaults to a ``documents`` subdirectory of ``STORAGE_LOCAL_PATH``,
    which docker-compose mounts as a writable volume owned by
    ``appuser``. Kept relative to the storage backend so deployments
    that override ``STORAGE_LOCAL_PATH`` stay consistent.

    In tests (``settings.TESTING``) the root is a process-wide temp
    directory instead — CI runs outside the compose mount, so the
    default ``/app/storage`` path is not writable there. Mirrors the
    media module's temp-storage fallback.
    """
    if settings.TESTING:
        return _test_documents_root()
    return Path(settings.STORAGE_LOCAL_PATH) / "documents"


_test_documents_root_cache: Path | None = None


def _test_documents_root() -> Path:
    """Return a cached per-process temp root for generated PDFs.

    Cached so ``generate_pdf`` and ``download_pdf`` resolve the same
    paths within a run (a fresh ``mkdtemp`` per call would orphan the
    file between the two requests under test).
    """
    global _test_documents_root_cache
    if _test_documents_root_cache is None:
        _test_documents_root_cache = (
            Path(tempfile.mkdtemp(prefix="dentalpin_test_documents_")) / "documents"
        )
    return _test_documents_root_cache


def _write_pdf_bytes(target: Path, data: bytes) -> None:
    """Write the rendered PDF, creating the per-clinic directory if needed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


class DocumentService:
    """Service layer for document CRUD and PDF generation."""

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        *,
        patient_id: uuid.UUID | None = None,
        document_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GeneratedDocument], int]:
        """List documents with optional filters, paginated."""
        query = select(GeneratedDocument).where(GeneratedDocument.clinic_id == clinic_id)
        if patient_id is not None:
            query = query.where(GeneratedDocument.patient_id == patient_id)
        if document_type is not None:
            query = query.where(GeneratedDocument.document_type == document_type)
        if status is not None:
            query = query.where(GeneratedDocument.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = query.order_by(GeneratedDocument.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        items = (await db.execute(query)).scalars().all()
        return list(items), total

    @staticmethod
    async def get_document(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> GeneratedDocument | None:
        """Get a single document by ID, scoped to clinic."""
        result = await db.execute(
            select(GeneratedDocument).where(
                GeneratedDocument.clinic_id == clinic_id,
                GeneratedDocument.id == document_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_document(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        *,
        patient_id: uuid.UUID,
        document_type: str,
        title: str,
        content: dict,
        created_by: uuid.UUID | None = None,
    ) -> GeneratedDocument | None:
        """Create a new document.

        Returns ``None`` when the patient does not belong to the calling
        clinic — callers surface that as a 400/403 so documents can
        never reference an out-of-clinic patient.
        """
        patient = await PatientService.get_patient(db, clinic_id, patient_id)
        if patient is None:
            return None

        doc = GeneratedDocument(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            patient_id=patient_id,
            document_type=document_type,
            title=title,
            status=DocumentStatus.DRAFT,
            content=content,
            created_by=created_by,
        )
        db.add(doc)
        await db.flush()
        return doc

    @staticmethod
    async def update_document(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        title: str | None = None,
        content: dict | None = None,
        status: str | None = None,
    ) -> GeneratedDocument | None:
        """Partial update of a document."""
        doc = await DocumentService.get_document(db, clinic_id, document_id)
        if doc is None:
            return None

        if title is not None:
            doc.title = title
        if content is not None:
            doc.content = content
        if status is not None:
            doc.status = status

        await db.flush()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> bool:
        """Soft-delete a document (set status to archived)."""
        doc = await DocumentService.get_document(db, clinic_id, document_id)
        if doc is None:
            return False
        doc.status = DocumentStatus.ARCHIVED
        await db.flush()
        return True

    @staticmethod
    async def _render_bytes(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        doc: GeneratedDocument,
        locale: str = "es",
    ) -> bytes:
        """Render a document as branded PDF bytes.

        Pulls the clinic (for the letterhead) and the patient (for the
        demographics block), then hands off to WeasyPrint off the event
        loop. Returns the raw PDF bytes.
        """
        from app.core.auth.models import Clinic

        clinic = await db.get(Clinic, clinic_id)
        patient = await PatientService.get_patient(db, clinic_id, doc.patient_id)
        issued_by = ""
        if doc.created_by is not None:
            from app.core.auth.models import User

            user = await db.get(User, doc.created_by)
            issued_by = f"{user.first_name} {user.last_name}" if user else ""
        return await DocumentPDFService.generate_pdf(doc, clinic, patient, locale, issued_by)

    @staticmethod
    async def generate_pdf(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
        locale: str = "es",
    ) -> GeneratedDocument | None:
        """Render a document, persist the branded PDF, publish the event.

        Rendering happens before the row is flipped to ``generated`` so
        a broken template surfaces loudly and no event is published for
        a document that has no real file behind it.

        Returns the updated document, or None if not found.
        """
        doc = await DocumentService.get_document(db, clinic_id, document_id)
        if doc is None:
            return None

        pdf_bytes = await DocumentService._render_bytes(db, clinic_id, doc, locale=locale)

        relative_path = f"documents/{clinic_id}/{doc.id}.pdf"
        target = _documents_root() / str(clinic_id) / f"{doc.id}.pdf"
        await asyncio.to_thread(_write_pdf_bytes, target, pdf_bytes)

        doc.status = DocumentStatus.GENERATED
        doc.file_path = relative_path
        await db.flush()

        payload: dict[str, str] = {
            "document_id": str(doc.id),
            "clinic_id": str(clinic_id),
            "patient_id": str(doc.patient_id),
            "document_type": doc.document_type,
            "title": doc.title,
        }
        if doc.created_by is not None:
            payload["created_by"] = str(doc.created_by)

        await event_bus.publish(EventType.DOCUMENT_GENERATED, payload, db=db)
        await db.refresh(doc)

        return doc

    @staticmethod
    async def download_pdf(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> bytes | None:
        """Return the persisted PDF for a generated document.

        Returns ``None`` when the document is unknown, not yet
        generated, or its rendered file is missing on disk.
        """
        doc = await DocumentService.get_document(db, clinic_id, document_id)
        if doc is None or doc.status != DocumentStatus.GENERATED or not doc.file_path:
            return None

        target = _documents_root() / str(clinic_id) / f"{doc.id}.pdf"
        try:
            return await asyncio.to_thread(target.read_bytes)
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            return None
