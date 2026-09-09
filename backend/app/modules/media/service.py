"""Business logic services for media module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import EventType, event_bus

from .attachment_registry import attachment_registry
from .exif import extract_captured_at
from .models import Document, MediaAttachment
from .photo_taxonomy import (
    MEDIA_KIND_PHOTO,
    MEDIA_KIND_XRAY,
    validate_media_classification,
)
from .storage import get_storage_backend
from .thumbnails import is_thumbnailable, store_thumbnails
from .validation import get_file_extension


class DocumentService:
    """CRUD + storage for documents (the file-level concerns)."""

    @staticmethod
    def generate_storage_path(
        clinic_id: UUID,
        patient_id: UUID,
        original_filename: str,
    ) -> str:
        """Return ``{clinic_id}/{patient_id}/{YYYY-MM}/{uuid}.{ext}``."""
        now = datetime.utcnow()
        year_month = now.strftime("%Y-%m")
        file_id = uuid4()
        ext = get_file_extension(original_filename)
        if ext:
            return f"{clinic_id}/{patient_id}/{year_month}/{file_id}.{ext}"
        return f"{clinic_id}/{patient_id}/{year_month}/{file_id}"

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        document_type: str | None = None,
        media_kind: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * page_size

        conditions = [
            Document.clinic_id == clinic_id,
            Document.patient_id == patient_id,
            Document.status == "active",
        ]
        if document_type:
            conditions.append(Document.document_type == document_type)
        if media_kind:
            conditions.append(Document.media_kind == media_kind)

        total = (await db.execute(select(func.count(Document.id)).where(*conditions))).scalar() or 0

        result = await db.execute(
            select(Document)
            .where(*conditions)
            .options(selectinload(Document.uploader))
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_document(
        db: AsyncSession,
        clinic_id: UUID,
        document_id: UUID,
    ) -> Document | None:
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.uploader))
            .where(Document.id == document_id, Document.clinic_id == clinic_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_document(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        user_id: UUID,
        file_data: bytes,
        original_filename: str,
        mime_type: str,
        document_type: str,
        title: str,
        description: str | None = None,
        media_kind: str = "document",
        media_category: str | None = None,
        media_subtype: str | None = None,
        captured_at: datetime | None = None,
        tags: list[str] | None = None,
        paired_document_id: UUID | None = None,
    ) -> Document:
        """Store the file (+thumbnails) and create the DB record.

        Photo-aware path: when ``media_kind`` is ``photo`` or ``xray``
        we generate thumb / medium derivatives next to the original and
        extract ``captured_at`` from EXIF when the caller did not pass
        one. Validation lives in ``photo_taxonomy``.
        """
        validate_media_classification(media_kind, media_category, media_subtype)

        if paired_document_id is not None:
            await PhotoService._validate_pair_target(db, clinic_id, patient_id, paired_document_id)

        storage = get_storage_backend()
        storage_path = DocumentService.generate_storage_path(
            clinic_id, patient_id, original_filename
        )
        await storage.store(file_data, storage_path)

        is_image_kind = media_kind in (MEDIA_KIND_PHOTO, MEDIA_KIND_XRAY)
        if is_image_kind and captured_at is None:
            captured_at = extract_captured_at(file_data)
        if is_image_kind and is_thumbnailable(mime_type):
            await store_thumbnails(storage, storage_path, file_data, mime_type)

        document = Document(
            clinic_id=clinic_id,
            patient_id=patient_id,
            document_type=document_type,
            title=title,
            description=description,
            original_filename=original_filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=len(file_data),
            media_kind=media_kind,
            media_category=media_category,
            media_subtype=media_subtype,
            captured_at=captured_at,
            paired_document_id=paired_document_id,
            tags=list(tags or []),
            uploaded_by=user_id,
        )
        db.add(document)
        await db.flush()

        # If pairing was requested, mirror it on the other side now that
        # the new document has an id.
        if paired_document_id is not None:
            other = await DocumentService.get_document(db, clinic_id, paired_document_id)
            if other is not None:
                other.paired_document_id = document.id
                await db.flush()

        await event_bus.publish(
            EventType.DOCUMENT_UPLOADED,
            {
                "document_id": str(document.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "title": title,
                "document_type": document_type,
                "media_kind": media_kind,
                "media_category": media_category,
                "media_subtype": media_subtype,
            },
        )
        if is_image_kind:
            await event_bus.publish(
                EventType.PHOTO_UPLOADED,
                {
                    "document_id": str(document.id),
                    "clinic_id": str(clinic_id),
                    "patient_id": str(patient_id),
                    "title": title,
                    "media_kind": media_kind,
                    "media_category": media_category,
                    "media_subtype": media_subtype,
                    "captured_at": captured_at.isoformat() if captured_at else None,
                },
            )

        await db.refresh(document, ["uploader"])
        return document

    @staticmethod
    async def update_document(
        db: AsyncSession,
        document: Document,
        data: dict,
    ) -> Document:
        for key, value in data.items():
            if value is not None:
                setattr(document, key, value)
        await db.flush()
        await db.refresh(document, ["uploader"])
        return document

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        document: Document,
    ) -> None:
        document.status = "archived"
        await db.flush()
        await event_bus.publish(
            EventType.DOCUMENT_DELETED,
            {
                "document_id": str(document.id),
                "clinic_id": str(document.clinic_id),
                "patient_id": str(document.patient_id),
            },
        )

    @staticmethod
    async def download_document(document: Document) -> bytes:
        storage = get_storage_backend()
        return await storage.retrieve(document.storage_path)

    @staticmethod
    async def archive_patient_documents(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
    ) -> int:
        result = await db.execute(
            select(Document).where(
                Document.clinic_id == clinic_id,
                Document.patient_id == patient_id,
                Document.status == "active",
            )
        )
        documents = list(result.scalars().all())
        for doc in documents:
            doc.status = "archived"
        await db.flush()
        return len(documents)

    @staticmethod
    async def unarchive_patient_documents(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
    ) -> int:
        """Reverse of :meth:`archive_patient_documents` — restores the
        documents archived with the patient (patient.restored cascade)."""
        result = await db.execute(
            select(Document).where(
                Document.clinic_id == clinic_id,
                Document.patient_id == patient_id,
                Document.status == "archived",
            )
        )
        documents = list(result.scalars().all())
        for doc in documents:
            doc.status = "active"
        await db.flush()
        return len(documents)


class PhotoService:
    """Photo-specific operations (gallery filters, pairing, metadata)."""

    @staticmethod
    async def list_photos(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        media_kind: str | None = None,
        media_category: str | None = None,
        media_subtype: str | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
        pair_status: str = "all",  # 'all' | 'paired' | 'unpaired'
        page: int = 1,
        page_size: int = 40,
    ) -> tuple[list[Document], int]:
        page_size = min(max(page_size, 1), 200)
        page = max(page, 1)
        offset = (page - 1) * page_size

        # Default kind filter: gallery shows photos AND xrays; documents
        # have their own list endpoint.
        kind_filter = (
            Document.media_kind.in_([MEDIA_KIND_PHOTO, MEDIA_KIND_XRAY])
            if media_kind is None
            else (Document.media_kind == media_kind)
        )

        conditions = [
            Document.clinic_id == clinic_id,
            Document.patient_id == patient_id,
            Document.status == "active",
            kind_filter,
        ]
        if media_category:
            conditions.append(Document.media_category == media_category)
        if media_subtype:
            conditions.append(Document.media_subtype == media_subtype)
        if captured_from:
            conditions.append(
                or_(
                    Document.captured_at >= captured_from,
                    and_(Document.captured_at.is_(None), Document.created_at >= captured_from),
                )
            )
        if captured_to:
            conditions.append(
                or_(
                    Document.captured_at <= captured_to,
                    and_(Document.captured_at.is_(None), Document.created_at <= captured_to),
                )
            )
        if pair_status == "paired":
            conditions.append(Document.paired_document_id.is_not(None))
        elif pair_status == "unpaired":
            conditions.append(Document.paired_document_id.is_(None))

        total = (await db.execute(select(func.count(Document.id)).where(*conditions))).scalar() or 0

        # Newest first; treat captured_at as a soft override on created_at.
        result = await db.execute(
            select(Document)
            .where(*conditions)
            .options(selectinload(Document.uploader))
            .order_by(
                func.coalesce(Document.captured_at, Document.created_at).desc(),
                Document.created_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def update_metadata(
        db: AsyncSession,
        document: Document,
        media_category: str | None = None,
        media_subtype: str | None = None,
        captured_at: datetime | None = None,
        tags: list[str] | None = None,
        paired_document_id: UUID | None = None,
    ) -> Document:
        new_category = media_category if media_category is not None else document.media_category
        new_subtype = media_subtype if media_subtype is not None else document.media_subtype
        validate_media_classification(document.media_kind, new_category, new_subtype)

        document.media_category = new_category
        document.media_subtype = new_subtype
        if captured_at is not None:
            document.captured_at = captured_at
        if tags is not None:
            document.tags = tags
        if paired_document_id is not None:
            await PhotoService._validate_pair_target(
                db, document.clinic_id, document.patient_id, paired_document_id
            )
            await PhotoService._set_pair(db, document, paired_document_id)
        await db.flush()
        await db.refresh(document, ["uploader"])
        return document

    @staticmethod
    async def pair(
        db: AsyncSession,
        clinic_id: UUID,
        document_a_id: UUID,
        document_b_id: UUID,
    ) -> tuple[Document, Document]:
        if document_a_id == document_b_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot pair a document with itself",
            )
        a = await DocumentService.get_document(db, clinic_id, document_a_id)
        b = await DocumentService.get_document(db, clinic_id, document_b_id)
        if not a or not b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both documents not found",
            )
        if a.patient_id != b.patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Documents must belong to the same patient",
            )
        a.paired_document_id = b.id
        b.paired_document_id = a.id
        await db.flush()
        await event_bus.publish(
            EventType.PAIR_CREATED,
            {
                "clinic_id": str(clinic_id),
                "patient_id": str(a.patient_id),
                "document_a_id": str(a.id),
                "document_b_id": str(b.id),
            },
        )
        return a, b

    @staticmethod
    async def unpair(db: AsyncSession, clinic_id: UUID, document_id: UUID) -> Document:
        doc = await DocumentService.get_document(db, clinic_id, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        partner_id = doc.paired_document_id
        doc.paired_document_id = None
        if partner_id:
            partner = await DocumentService.get_document(db, clinic_id, partner_id)
            if partner is not None and partner.paired_document_id == doc.id:
                partner.paired_document_id = None
        await db.flush()
        if partner_id:
            await event_bus.publish(
                EventType.PAIR_REMOVED,
                {
                    "clinic_id": str(clinic_id),
                    "patient_id": str(doc.patient_id),
                    "document_id": str(doc.id),
                    "former_partner_id": str(partner_id),
                },
            )
        return doc

    @staticmethod
    async def _validate_pair_target(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        target_id: UUID,
    ) -> None:
        target = await DocumentService.get_document(db, clinic_id, target_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pair target document not found",
            )
        if target.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Pair target must belong to the same patient",
            )

    @staticmethod
    async def _set_pair(db: AsyncSession, document: Document, partner_id: UUID) -> None:
        document.paired_document_id = partner_id
        partner = await DocumentService.get_document(db, document.clinic_id, partner_id)
        if partner is not None:
            partner.paired_document_id = document.id


class AttachmentService:
    """Polymorphic attachment plumbing — owner registry + CRUD."""

    @staticmethod
    async def link(
        db: AsyncSession,
        clinic_id: UUID,
        document_id: UUID,
        owner_type: str,
        owner_id: UUID,
        display_order: int = 0,
    ) -> MediaAttachment:
        if not attachment_registry.has(owner_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unknown owner_type '{owner_type}'. "
                    f"Known: {', '.join(attachment_registry.known_types())}"
                ),
            )

        document = await DocumentService.get_document(db, clinic_id, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        owner_patient_id = await attachment_registry.resolve_patient_id(
            db, clinic_id, owner_type, owner_id
        )
        if owner_patient_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Owner ({owner_type}, {owner_id}) not found in this clinic",
            )
        if owner_patient_id != document.patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document and owner belong to different patients",
            )

        # Idempotent: return existing if already linked.
        existing = await db.execute(
            select(MediaAttachment).where(
                MediaAttachment.clinic_id == clinic_id,
                MediaAttachment.document_id == document_id,
                MediaAttachment.owner_type == owner_type,
                MediaAttachment.owner_id == owner_id,
            )
        )
        already = existing.scalar_one_or_none()
        if already is not None:
            return already

        attachment = MediaAttachment(
            clinic_id=clinic_id,
            document_id=document_id,
            owner_type=owner_type,
            owner_id=owner_id,
            display_order=display_order,
        )
        db.add(attachment)
        await db.flush()
        await db.refresh(attachment, ["document"])

        await event_bus.publish(
            EventType.ATTACHMENT_LINKED,
            {
                "attachment_id": str(attachment.id),
                "clinic_id": str(clinic_id),
                "document_id": str(document_id),
                "owner_type": owner_type,
                "owner_id": str(owner_id),
                "patient_id": str(document.patient_id),
            },
        )
        return attachment

    @staticmethod
    async def unlink(
        db: AsyncSession,
        clinic_id: UUID,
        attachment_id: UUID,
    ) -> None:
        result = await db.execute(
            select(MediaAttachment).where(
                MediaAttachment.id == attachment_id,
                MediaAttachment.clinic_id == clinic_id,
            )
        )
        attachment = result.scalar_one_or_none()
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )
        owner_type = attachment.owner_type
        owner_id = attachment.owner_id
        document_id = attachment.document_id
        await db.delete(attachment)
        await db.flush()
        await event_bus.publish(
            EventType.ATTACHMENT_UNLINKED,
            {
                "attachment_id": str(attachment_id),
                "clinic_id": str(clinic_id),
                "document_id": str(document_id),
                "owner_type": owner_type,
                "owner_id": str(owner_id),
            },
        )

    @staticmethod
    async def list_by_owner(
        db: AsyncSession,
        clinic_id: UUID,
        owner_type: str,
        owner_id: UUID,
    ) -> list[MediaAttachment]:
        result = await db.execute(
            select(MediaAttachment)
            .options(selectinload(MediaAttachment.document))
            .where(
                MediaAttachment.clinic_id == clinic_id,
                MediaAttachment.owner_type == owner_type,
                MediaAttachment.owner_id == owner_id,
            )
            .order_by(MediaAttachment.display_order.asc(), MediaAttachment.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def unlink_all_for_owner(
        db: AsyncSession,
        clinic_id: UUID,
        owner_type: str,
        owner_id: UUID,
    ) -> int:
        """Bulk-unlink helper used by owner modules on their own deletes."""
        result = await db.execute(
            select(MediaAttachment).where(
                MediaAttachment.clinic_id == clinic_id,
                MediaAttachment.owner_type == owner_type,
                MediaAttachment.owner_id == owner_id,
            )
        )
        rows = list(result.scalars().all())
        for row in rows:
            await db.delete(row)
        await db.flush()
        return len(rows)
