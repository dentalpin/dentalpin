"""Business logic for the documents module.

All functions are stateless static methods on ``DocumentService``.
Every query filters by ``clinic_id`` (multi-tenancy, mandatory).
"""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.events.types import EventType
from .models import DocumentStatus, DocumentType, GeneratedDocument


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
        query = select(GeneratedDocument).where(
            GeneratedDocument.clinic_id == clinic_id
        )
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
    ) -> GeneratedDocument:
        """Create a new document."""
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
    async def generate_pdf(
        db: AsyncSession,
        clinic_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> GeneratedDocument | None:
        """Generate (render) a document and publish DOCUMENT_GENERATED.

        The actual PDF rendering is handled by the PDF generation service
        (Jinja2 + WeasyPrint or similar). This method marks the document
        as generated and publishes the event for activity_journal pickup.

        Returns the updated document, or None if not found.
        """
        doc = await DocumentService.get_document(db, clinic_id, document_id)
        if doc is None:
            return None

        # In production this calls the PDF renderer to produce the file.
        # For now, mark as generated and publish the event.
        doc.status = DocumentStatus.GENERATED
        doc.file_path = f"documents/{clinic_id}/{doc.id}.pdf"
        await db.flush()

        await event_bus.publish(
            EventType.DOCUMENT_GENERATED,
            {
                "document_id": str(doc.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(doc.patient_id),
                "document_type": doc.document_type,
                "title": doc.title,
            },
        )

        return doc
