"""Domain operations for clinic-scoped consent and immutable signatures."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from urllib.parse import urlparse

import qrcode
from PIL import Image, UnidentifiedImageError
from qrcode.constants import ERROR_CORRECT_M
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic
from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.pdf_locales import PDF_LOCALES
from app.core.utils.dates import clinic_today, clinic_zone
from app.modules.patients.service import PatientService

from .consent_markdown import render_consent_body
from .consent_variables import build_values, fill_template_variables
from .exceptions import (
    ConsentConflictError,
    ConsentNotFoundError,
    ConsentStorageError,
    ConsentValidationError,
)
from .models import ConsentEvidence, ConsentSigningLink, ConsentTemplate, GeneratedDocument
from .pdf import DocumentPDFService
from .service import _documents_root, _write_pdf_bytes

Purpose = Literal["sign", "revoke"]

ID_DOCUMENT_MAX_LENGTH = 32
# Deliberately loose charset (letters, digits, "-", ".", "/"); no country-specific checksum.


def _normalize_id_document(value: str | None, relationship: str) -> str | None:
    """Remove whitespace + uppercase the signer's ID document; required unless the signer is the patient.

    Whitespace is dropped (``"1234 5678 z"`` -> ``"12345678Z"``) because IDs are often
    written in groups; no country-specific checksum is applied.
    """
    normalized = "".join((value or "").split()).upper()
    if not normalized:
        if relationship != "patient":
            raise ConsentValidationError(
                "Signer ID document required for guardian or representative"
            )
        return None
    if len(normalized) > ID_DOCUMENT_MAX_LENGTH or not all(
        ch.isalnum() or ch in "-./" for ch in normalized
    ):
        raise ConsentValidationError("Signer ID document is invalid")
    return normalized


def _signing_url(token: str) -> str:
    """Use the configured patient-facing origin, matching agenda check-in."""
    origins = settings.allowed_origins_list
    try:
        parsed = urlparse(origins[0]) if origins else None
    except ValueError:
        parsed = None
    if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConsentValidationError("Set ALLOWED_ORIGINS to an http(s) patient-facing origin")
    return f"{parsed.scheme}://{parsed.netloc}/p/consent#{token}"


def _signing_qr(url: str) -> str:
    """Return a PNG data URL without sending its bearer link to a third party."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    png = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(png, format="PNG")
    return "data:image/png;base64," + base64.b64encode(png.getvalue()).decode("ascii")


def _template(t: ConsentTemplate) -> dict:
    return {"id": str(t.id), "title": t.title, "body": t.body, "is_active": t.is_active}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _signature_data(value: str) -> str:
    prefix = "data:image/png;base64,"
    if not value.startswith(prefix):
        raise ConsentValidationError("A PNG signature is required")
    try:
        data = base64.b64decode(value[len(prefix) :], validate=True)
        if not data or len(data) > 1024 * 1024:
            raise ValueError("invalid size")
        with Image.open(io.BytesIO(data)) as img:
            if img.format != "PNG" or img.width * img.height > 4_000_000:
                raise ValueError("invalid dimensions")
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            image = img.convert("RGBA")
            background = Image.new("RGBA", image.size, "white")
            background.alpha_composite(image)
            if background.convert("L").getextrema()[0] >= 250:
                raise ValueError("blank signature")
    except (ValueError, OSError, UnidentifiedImageError):
        raise ConsentValidationError("Invalid PNG signature") from None
    return prefix + base64.b64encode(data).decode("ascii")


async def _document(
    db: AsyncSession, clinic_id: uuid.UUID, doc_id: uuid.UUID, *, lock: bool = False
) -> GeneratedDocument:
    stmt = select(GeneratedDocument).where(
        GeneratedDocument.id == doc_id,
        GeneratedDocument.clinic_id == clinic_id,
        GeneratedDocument.document_type == "informed_consent",
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if doc is None:
        raise ConsentNotFoundError("Consent not found")
    return doc


async def _evidence(
    db: AsyncSession, doc_id: uuid.UUID, purpose: Purpose
) -> ConsentEvidence | None:
    return (
        await db.execute(
            select(ConsentEvidence).where(
                ConsentEvidence.document_id == doc_id,
                ConsentEvidence.purpose == purpose,
            )
        )
    ).scalar_one_or_none()


async def _link(db: AsyncSession, token: str) -> ConsentSigningLink:
    if len(token) > 128:
        raise ConsentNotFoundError("Link not found")
    link = (
        await db.execute(
            select(ConsentSigningLink).where(ConsentSigningLink.token_hash == _token_hash(token))
        )
    ).scalar_one_or_none()
    if not link or link.used_at or link.expires_at <= datetime.now(UTC):
        raise ConsentNotFoundError("Link not found or expired")
    return link


class ConsentService:
    """Clinic-scoped consent operations; HTTP transport is handled by the router."""

    @staticmethod
    async def list_templates(ctx, db, include_archived: bool = False):
        stmt = select(ConsentTemplate).where(ConsentTemplate.clinic_id == ctx.clinic_id)
        if not include_archived:
            stmt = stmt.where(ConsentTemplate.is_active.is_(True))
        rows = (
            await db.execute(stmt.order_by(ConsentTemplate.title, ConsentTemplate.id))
        ).scalars()
        return {"data": [_template(t) for t in rows]}

    @staticmethod
    async def create_template(data, ctx, db):
        title, body = data.title.strip(), data.body.strip()
        if not title or not body:
            raise ConsentValidationError("Title and text are required")
        t = ConsentTemplate(id=uuid.uuid4(), clinic_id=ctx.clinic_id, title=title, body=body)
        db.add(t)
        await db.flush()
        return {"data": _template(t)}

    @staticmethod
    async def _clinic_template(template_id, ctx, db) -> ConsentTemplate:
        t = (
            await db.execute(
                select(ConsentTemplate).where(
                    ConsentTemplate.id == template_id, ConsentTemplate.clinic_id == ctx.clinic_id
                )
            )
        ).scalar_one_or_none()
        if t is None:
            raise ConsentNotFoundError("Template not found")
        return t

    @staticmethod
    async def set_template_active(template_id, active: bool, ctx, db):
        """Archive (hide from the picker) or restore a template; idempotent."""
        t = await ConsentService._clinic_template(template_id, ctx, db)
        t.is_active = active
        await db.flush()
        return {"data": _template(t)}

    @staticmethod
    async def update_template(template_id, data, ctx, db):
        t = await ConsentService._clinic_template(template_id, ctx, db)
        if not data.title.strip() or not data.body.strip():
            raise ConsentValidationError("Title and text are required")
        t.title, t.body = data.title.strip(), data.body.strip()
        await db.flush()
        return {"data": _template(t)}

    @staticmethod
    async def consent_signature_status(patient_id, ctx, db, record_access):
        """Return signature state for one clinic-scoped patient's consents."""
        patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
        if patient is None:
            raise ConsentNotFoundError("Patient not found")
        signed = exists().where(
            ConsentEvidence.clinic_id == ctx.clinic_id,
            ConsentEvidence.document_id == GeneratedDocument.id,
            ConsentEvidence.purpose == "sign",
        )
        revoked = exists().where(
            ConsentEvidence.clinic_id == ctx.clinic_id,
            ConsentEvidence.document_id == GeneratedDocument.id,
            ConsentEvidence.purpose == "revoke",
        )
        rows = (
            await db.execute(
                select(
                    GeneratedDocument.id, signed.label("signed"), revoked.label("revoked")
                ).where(
                    GeneratedDocument.clinic_id == ctx.clinic_id,
                    GeneratedDocument.patient_id == patient_id,
                    GeneratedDocument.document_type == "informed_consent",
                )
            )
        ).all()
        if rows:
            await record_access(patient_id, "documents")
        return {
            "data": [
                {"id": str(row.id), "signed": row.signed, "revoked": row.revoked} for row in rows
            ]
        }

    @staticmethod
    async def create_consent(data, ctx, db):
        template = (
            await db.execute(
                select(ConsentTemplate).where(
                    ConsentTemplate.id == data.template_id,
                    ConsentTemplate.clinic_id == ctx.clinic_id,
                )
            )
        ).scalar_one_or_none()
        patient = await PatientService.get_patient(db, ctx.clinic_id, data.patient_id)
        if template is None or patient is None:
            raise ConsentNotFoundError("Patient or template not found")
        if not template.is_active:
            raise ConsentConflictError("Archived templates cannot be used for new consents")
        clinic = ctx.clinic
        communication_language = (clinic.settings or {}).get("communication_language", "es")
        locale = communication_language if communication_language in PDF_LOCALES else "en"
        text, unknown = fill_template_variables(
            template.body,
            build_values(
                patient=patient,
                clinic_name=DocumentPDFService._letterhead(clinic)["name"],
                user=ctx.user,
                today=clinic_today(clinic.timezone),
                locale=locale,
            ),
        )
        doc = GeneratedDocument(
            id=uuid.uuid4(),
            clinic_id=ctx.clinic_id,
            patient_id=data.patient_id,
            document_type="informed_consent",
            title=template.title,
            status="draft",
            content={"text": text},
            created_by=ctx.user_id,
        )
        db.add(doc)
        await db.flush()
        data = {"id": str(doc.id)}
        if unknown:
            data["unknown_variables"] = unknown
        return {"data": data}

    @staticmethod
    async def create_link(document_id, purpose, ctx, db, locale):
        doc = await _document(db, ctx.clinic_id, document_id, lock=True)
        if doc.status == "archived":
            raise ConsentConflictError("Archived consents cannot be signed")
        signed = await _evidence(db, doc.id, "sign")
        revoked = await _evidence(db, doc.id, "revoke")
        if (purpose == "sign" and signed) or (purpose == "revoke" and (not signed or revoked)):
            raise ConsentConflictError("Consent is not eligible for this operation")
        clinic = await db.get(Clinic, ctx.clinic_id)
        clinic_locale = (
            (clinic.settings or {}).get("communication_language", "es") if clinic else "es"
        )
        selected_locale = locale or (clinic_locale if clinic_locale in PDF_LOCALES else "en")
        token = secrets.token_urlsafe(32)
        url = _signing_url(token)
        qr_data_url = await asyncio.to_thread(_signing_qr, url)
        expires = datetime.now(UTC) + timedelta(minutes=30)
        db.add(
            ConsentSigningLink(
                id=uuid.uuid4(),
                clinic_id=ctx.clinic_id,
                document_id=doc.id,
                token_hash=_token_hash(token),
                purpose=purpose,
                locale=selected_locale,
                expires_at=expires,
            )
        )
        await db.flush()
        return {
            "data": {
                "token": token,
                "url": url,
                "qr_data_url": qr_data_url,
                "expires_at": expires.isoformat(),
            }
        }

    @staticmethod
    async def public_consent(db, token):
        initial = await _link(db, token)
        # Recheck the link after acquiring the same document lock as edits and
        # signing: a view that raced an edit must not reveal the changed text.
        doc = await _document(db, initial.clinic_id, initial.document_id, lock=True)
        link = (
            await db.execute(
                select(ConsentSigningLink)
                .where(ConsentSigningLink.id == initial.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        if (
            link.used_at
            or link.expires_at <= datetime.now(UTC)
            or doc.status == "archived"
            or await _evidence(db, doc.id, link.purpose)
        ):
            raise ConsentNotFoundError("Link not found or expired")
        patient = await PatientService.get_patient(db, link.clinic_id, doc.patient_id)
        clinic = await db.get(Clinic, link.clinic_id)
        if not patient or not clinic:
            raise ConsentNotFoundError("Consent not found")
        return {
            "data": {
                "title": doc.title,
                "text": doc.content["text"],
                # The page renders this, never ``text`` (#1171). Same renderer as the PDF.
                "body_html": render_consent_body(doc.content["text"]),
                "patient": f"{patient.first_name} {patient.last_name}",
                "clinic": clinic.name,
                "purpose": link.purpose,
                "locale": link.locale,
            }
        }

    @staticmethod
    async def sign_consent(data, db, token, client_ip, user_agent):
        signature = _signature_data(data.signature)
        name = data.signer_name.strip()
        if not name:
            raise ConsentValidationError("Signer name required")
        id_document = _normalize_id_document(data.signer_id_document, data.relationship_to_patient)
        initial = await _link(db, token)
        doc = await _document(db, initial.clinic_id, initial.document_id, lock=True)
        link = (
            await db.execute(
                select(ConsentSigningLink)
                .where(ConsentSigningLink.id == initial.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        now = datetime.now(UTC)
        if (
            doc.status == "archived"
            or link.used_at
            or link.expires_at <= now
            or await _evidence(db, doc.id, link.purpose)
        ):
            raise ConsentConflictError("Link is no longer valid")
        if link.purpose == "revoke" and not await _evidence(db, doc.id, "sign"):
            raise ConsentConflictError("Consent is not signed")
        patient = await PatientService.get_patient(db, link.clinic_id, doc.patient_id)
        clinic = await db.get(Clinic, link.clinic_id)
        if not patient or not clinic:
            raise ConsentNotFoundError("Consent not found")
        content = {
            **doc.content,
            "signature": signature,
            "signer_name": name,
            "relationship_to_patient": data.relationship_to_patient,
            "signer_id_document": id_document,
            "signed_at": now.astimezone(clinic_zone(clinic.timezone)).strftime("%d/%m/%Y %H:%M %Z"),
            "purpose": link.purpose,
        }
        snapshot = SimpleNamespace(
            document_type="informed_consent", content=content, title=doc.title
        )
        pdf = await DocumentPDFService.generate_pdf(snapshot, clinic, patient, link.locale)
        if not pdf.startswith(b"%PDF-"):
            raise ConsentStorageError("PDF generation failed")
        evidence_id = uuid.uuid4()
        target = _documents_root() / str(link.clinic_id) / f"consent-{evidence_id}.pdf"
        await asyncio.to_thread(_write_pdf_bytes, target, pdf)
        stored_pdf = await asyncio.to_thread(target.read_bytes)
        if stored_pdf != pdf:
            raise ConsentStorageError("Signed PDF could not be stored intact")
        db.add(
            ConsentEvidence(
                id=evidence_id,
                clinic_id=link.clinic_id,
                document_id=doc.id,
                purpose=link.purpose,
                signer_name=name,
                relationship_to_patient=data.relationship_to_patient,
                signer_id_document=id_document,
                signed_at=now,
                ip_address=client_ip[:45] if client_ip else None,
                user_agent=user_agent[:1000],
                sha256=hashlib.sha256(stored_pdf).hexdigest(),
                file_path=f"documents/{link.clinic_id}/consent-{evidence_id}.pdf",
            )
        )
        link.used_at = now
        if link.purpose == "sign":
            doc.status = "generated"
            doc.file_path = f"documents/{link.clinic_id}/consent-{evidence_id}.pdf"
        await db.flush()
        if link.purpose == "sign":
            payload = {
                "document_id": str(doc.id),
                "clinic_id": str(doc.clinic_id),
                "patient_id": str(doc.patient_id),
                "document_type": doc.document_type,
                "title": doc.title,
            }
            if doc.created_by is not None:
                payload["created_by"] = str(doc.created_by)
            await event_bus.publish(EventType.DOCUMENT_GENERATED, payload, db=db)
        return {"data": {"signed": True}}

    @staticmethod
    async def list_evidence(document_id, ctx, db, record_access):
        doc = await _document(db, ctx.clinic_id, document_id)
        rows = (
            await db.execute(
                select(ConsentEvidence).where(
                    ConsentEvidence.document_id == document_id,
                    ConsentEvidence.clinic_id == ctx.clinic_id,
                )
            )
        ).scalars()
        await record_access(doc.patient_id, "documents")
        return {
            "data": [
                {
                    "purpose": e.purpose,
                    "signed_at": e.signed_at.isoformat(),
                    "signer_name": e.signer_name,
                    "relationship_to_patient": e.relationship_to_patient,
                    "signer_id_document": e.signer_id_document,
                    "ip_address": e.ip_address,
                    "user_agent": e.user_agent,
                    "sha256": e.sha256,
                }
                for e in rows
            ]
        }

    @staticmethod
    async def download_evidence(document_id, purpose, ctx, db, record_access):
        doc = await _document(db, ctx.clinic_id, document_id)
        evidence = await _evidence(db, doc.id, purpose)
        if evidence is None:
            raise ConsentNotFoundError("Evidence not found")
        target = _documents_root() / str(ctx.clinic_id) / f"consent-{evidence.id}.pdf"
        try:
            data = await asyncio.to_thread(Path.read_bytes, target)
        except OSError:
            raise ConsentNotFoundError("Evidence file missing") from None
        if not secrets.compare_digest(hashlib.sha256(data).hexdigest(), evidence.sha256):
            raise ConsentConflictError("Evidence file integrity check failed")
        await record_access(doc.patient_id, "document_pdf", action="download")
        return data
