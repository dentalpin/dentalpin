import asyncio
import uuid
from datetime import UTC, date, datetime
from io import BytesIO

from jinja2 import Template
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.core.auth.models import Clinic
from app.core.events.bus import event_bus
from app.core.events.types import EventType
from app.modules.media.service import DocumentService as MediaDocumentService
from app.modules.patients.models import Patient

from .models import GeneratedDocument, Letterhead
from .schemas import (
    CertificateCreate,
    LetterheadCreate,
    LetterheadUpdate,
    PrescriptionCreate,
    RadiologyRequestCreate,
    ReferralCreate,
)
from .templates import TEMPLATES_BY_TYPE

DOC_TITLES = {
    "prescription": "Prescription",
    "certificate": "Medical Certificate",
    "referral": "Referral Letter",
    "radiology_request": "Radiology Request",
}


class LetterheadService:
    @staticmethod
    async def get(db: AsyncSession, clinic_id: uuid.UUID) -> Letterhead | None:
        result = await db.execute(
            select(Letterhead).where(Letterhead.clinic_id == clinic_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession, clinic_id: uuid.UUID, data: LetterheadCreate | LetterheadUpdate
    ) -> Letterhead:
        letterhead = await LetterheadService.get(db, clinic_id)
        payload = data.model_dump(exclude_unset=True)
        if letterhead is None:
            letterhead = Letterhead(clinic_id=clinic_id, **payload)
            db.add(letterhead)
        else:
            for key, value in payload.items():
                setattr(letterhead, key, value)
        await db.commit()
        await db.refresh(letterhead)
        return letterhead


class DocumentPDFService:
    """HTML -> PDF pipeline. Mirrors the pattern used in budget/pdf.py
    and billing/pdf.py so WeasyPrint calls stay off the event loop."""

    @staticmethod
    async def render_html(document_type: str, context: dict) -> str:
        template = Template(TEMPLATES_BY_TYPE[document_type])
        return template.render(**context)

    @staticmethod
    async def generate_pdf(html: str) -> bytes:
        return await asyncio.to_thread(DocumentPDFService._html_to_pdf, html)

    @staticmethod
    def _html_to_pdf(html: str) -> bytes:
        pdf = BytesIO()
        HTML(string=html).write_pdf(pdf)
        return pdf.getvalue()


class DocumentService:
    """Creates a GeneratedDocument for each document type: builds the
    render context, renders HTML, converts to PDF, stores the PDF via the
    media module, persists the row, and publishes DOCUMENT_GENERATED."""

    @staticmethod
    async def _load_patient(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
        patient = await db.get(Patient, patient_id)
        if patient is None:
            raise ValueError(f"Patient {patient_id} not found")
        return patient

    @staticmethod
    async def _finalize(
        db: AsyncSession,
        *,
        clinic_id: uuid.UUID,
        patient_id: uuid.UUID,
        created_by: uuid.UUID,
        document_type: str,
        title: str,
        context: dict,
        payload: dict,
    ) -> GeneratedDocument:
        clinic = await db.get(Clinic, clinic_id)
        letterhead = await LetterheadService.get(db, clinic_id)

        render_context = {
            **context,
            "clinic": clinic,
            "letterhead": letterhead,
            "title": title,
            "generated_date": date.today().isoformat(),
        }
        html = await DocumentPDFService.render_html(document_type, render_context)
        pdf_bytes = await DocumentPDFService.generate_pdf(html)

        media_doc = await MediaDocumentService.create_document(
            db=db,
            clinic_id=clinic_id,
            patient_id=patient_id,
            document_type="report",
            title=title,
            file_data=pdf_bytes,
            original_filename=f"{document_type}.pdf",
            mime_type="application/pdf",
            user_id=created_by,
        )

        doc = GeneratedDocument(
            clinic_id=clinic_id,
            patient_id=patient_id,
            created_by=created_by,
            document_type=document_type,
            title=title,
            content_html=html,
            payload=payload,
            media_document_id=getattr(media_doc, "id", None),
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        await event_bus.publish(
            EventType.DOCUMENT_GENERATED,
            {
                "doc_id": str(doc.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "doc_type": doc.document_type,
                "generated_at": datetime.now(UTC).isoformat(),
            },
        )
        return doc

    @staticmethod
    async def create_prescription(
        db: AsyncSession, clinic_id: uuid.UUID, created_by: uuid.UUID, data: PrescriptionCreate
    ) -> GeneratedDocument:
        patient = await DocumentService._load_patient(db, data.patient_id)
        return await DocumentService._finalize(
            db,
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            created_by=created_by,
            document_type="prescription",
            title=DOC_TITLES["prescription"],
            context={
                "patient": patient,
                "items": [item.model_dump() for item in data.items],
                "notes": data.notes,
            },
            payload=data.model_dump(mode="json"),
        )

    @staticmethod
    async def create_certificate(
        db: AsyncSession, clinic_id: uuid.UUID, created_by: uuid.UUID, data: CertificateCreate
    ) -> GeneratedDocument:
        patient = await DocumentService._load_patient(db, data.patient_id)
        return await DocumentService._finalize(
            db,
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            created_by=created_by,
            document_type="certificate",
            title=DOC_TITLES["certificate"],
            context={
                "patient": patient,
                "certificate_type": data.certificate_type,
                "start_date": data.start_date.isoformat() if data.start_date else None,
                "end_date": data.end_date.isoformat() if data.end_date else None,
                "reason": data.reason,
                "notes": data.notes,
            },
            payload=data.model_dump(mode="json"),
        )

    @staticmethod
    async def create_referral(
        db: AsyncSession, clinic_id: uuid.UUID, created_by: uuid.UUID, data: ReferralCreate
    ) -> GeneratedDocument:
        patient = await DocumentService._load_patient(db, data.patient_id)
        return await DocumentService._finalize(
            db,
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            created_by=created_by,
            document_type="referral",
            title=DOC_TITLES["referral"],
            context={
                "patient": patient,
                "specialist_name": data.specialist_name,
                "specialty": data.specialty,
                "reason": data.reason,
                "clinical_history": data.clinical_history,
                "urgency": data.urgency,
            },
            payload=data.model_dump(mode="json"),
        )

    @staticmethod
    async def create_radiology_request(
        db: AsyncSession, clinic_id: uuid.UUID, created_by: uuid.UUID, data: RadiologyRequestCreate
    ) -> GeneratedDocument:
        patient = await DocumentService._load_patient(db, data.patient_id)
        return await DocumentService._finalize(
            db,
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            created_by=created_by,
            document_type="radiology_request",
            title=DOC_TITLES["radiology_request"],
            context={
                "patient": patient,
                "exam_type": data.exam_type,
                "tooth_reference": data.tooth_reference,
                "clinical_indication": data.clinical_indication,
                "notes": data.notes,
            },
            payload=data.model_dump(mode="json"),
        )

    @staticmethod
    async def get(db: AsyncSession, clinic_id: uuid.UUID, doc_id: uuid.UUID) -> GeneratedDocument | None:
        result = await db.execute(
            select(GeneratedDocument).where(
                GeneratedDocument.id == doc_id, GeneratedDocument.clinic_id == clinic_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession, clinic_id: uuid.UUID, document_type: str | None = None,
        patient_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0,
    ) -> tuple[list[GeneratedDocument], int]:
        base_filters = [GeneratedDocument.clinic_id == clinic_id]
        if document_type:
            base_filters.append(GeneratedDocument.document_type == document_type)
        if patient_id:
            base_filters.append(GeneratedDocument.patient_id == patient_id)

        count_result = await db.execute(
            select(func.count()).select_from(GeneratedDocument).where(*base_filters)
        )
        total = count_result.scalar_one()

        query = (
            select(GeneratedDocument)
            .where(*base_filters)
            .order_by(GeneratedDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return list(result.scalars().all()), total
