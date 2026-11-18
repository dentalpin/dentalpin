"""Clinic-scoped informed consent templates and one-use tablet signatures."""

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
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.models import Clinic
from app.core.auth.router import limiter
from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.patient_access import RecordPatientAccess
from app.database import get_db
from app.modules.patients.service import PatientService

from .models import ConsentEvidence, ConsentSigningLink, ConsentTemplate, GeneratedDocument
from .pdf import DocumentPDFService
from .service import _documents_root, _write_pdf_bytes

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]
Ctx = Annotated[ClinicContext, Depends(get_clinic_context)]
Read = Annotated[None, Depends(require_permission("documents.read"))]
Write = Annotated[None, Depends(require_permission("documents.write"))]
Purpose = Literal["sign", "revoke"]


def _bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(404, "Link not found or expired")
    token = authorization.removeprefix("Bearer ")
    if not token or len(token) > 128:
        raise HTTPException(404, "Link not found or expired")
    return token


Token = Annotated[str, Depends(_bearer_token)]


class TemplateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=30000)


class CreateConsent(BaseModel):
    patient_id: uuid.UUID
    template_id: uuid.UUID


class SignConsent(BaseModel):
    signer_name: str = Field(min_length=1, max_length=200)
    relationship_to_patient: Literal["patient", "guardian", "representative"]
    signature: str = Field(min_length=1, max_length=1500000)


def _template(t: ConsentTemplate) -> dict:
    return {"id": str(t.id), "title": t.title, "body": t.body}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _signature_data(value: str) -> str:
    prefix = "data:image/png;base64,"
    if not value.startswith(prefix):
        raise HTTPException(422, "A PNG signature is required")
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
        raise HTTPException(422, "Invalid PNG signature") from None
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
        raise HTTPException(404, "Consent not found")
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


@router.get("/consent-templates")
async def list_templates(ctx: Ctx, _: Read, db: Db) -> dict:
    rows = (
        await db.execute(
            select(ConsentTemplate)
            .where(ConsentTemplate.clinic_id == ctx.clinic_id)
            .order_by(ConsentTemplate.title, ConsentTemplate.id)
        )
    ).scalars()
    return {"data": [_template(t) for t in rows]}


@router.post("/consent-templates", status_code=201)
async def create_template(data: TemplateBody, ctx: Ctx, _: Write, db: Db) -> dict:
    title, body = data.title.strip(), data.body.strip()
    if not title or not body:
        raise HTTPException(422, "Title and text are required")
    t = ConsentTemplate(id=uuid.uuid4(), clinic_id=ctx.clinic_id, title=title, body=body)
    db.add(t)
    await db.flush()
    return {"data": _template(t)}


@router.put("/consent-templates/{template_id}")
async def update_template(
    template_id: uuid.UUID, data: TemplateBody, ctx: Ctx, _: Write, db: Db
) -> dict:
    t = (
        await db.execute(
            select(ConsentTemplate).where(
                ConsentTemplate.id == template_id, ConsentTemplate.clinic_id == ctx.clinic_id
            )
        )
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Template not found")
    if not data.title.strip() or not data.body.strip():
        raise HTTPException(422, "Title and text are required")
    t.title, t.body = data.title.strip(), data.body.strip()
    await db.flush()
    return {"data": _template(t)}


@router.get("/consents/signature-status")
async def consent_signature_status(
    patient_id: uuid.UUID, ctx: Ctx, _: Read, db: Db, record_access: RecordPatientAccess
) -> dict:
    """Return signature state for one clinic-scoped patient's consents."""
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    signed = exists().where(
        ConsentEvidence.clinic_id == ctx.clinic_id,
        ConsentEvidence.document_id == GeneratedDocument.id,
        ConsentEvidence.purpose == "sign",
    )
    rows = (
        await db.execute(
            select(GeneratedDocument.id, signed.label("signed")).where(
                GeneratedDocument.clinic_id == ctx.clinic_id,
                GeneratedDocument.patient_id == patient_id,
                GeneratedDocument.document_type == "informed_consent",
            )
        )
    ).all()
    if rows:
        await record_access(patient_id, "documents")
    return {"data": [{"id": str(row.id), "signed": row.signed} for row in rows]}


@router.post("/consents", status_code=201)
async def create_consent(data: CreateConsent, ctx: Ctx, _: Write, db: Db) -> dict:
    template = (
        await db.execute(
            select(ConsentTemplate).where(
                ConsentTemplate.id == data.template_id, ConsentTemplate.clinic_id == ctx.clinic_id
            )
        )
    ).scalar_one_or_none()
    patient = await PatientService.get_patient(db, ctx.clinic_id, data.patient_id)
    if template is None or patient is None:
        raise HTTPException(404, "Patient or template not found")
    doc = GeneratedDocument(
        id=uuid.uuid4(),
        clinic_id=ctx.clinic_id,
        patient_id=data.patient_id,
        document_type="informed_consent",
        title=template.title,
        status="draft",
        content={"text": template.body},
        created_by=ctx.user_id,
    )
    db.add(doc)
    await db.flush()
    return {"data": {"id": str(doc.id)}}


@router.post("/consents/{document_id}/links", status_code=201)
async def create_link(document_id: uuid.UUID, purpose: Purpose, ctx: Ctx, _: Write, db: Db) -> dict:
    doc = await _document(db, ctx.clinic_id, document_id, lock=True)
    if doc.status == "archived":
        raise HTTPException(409, "Archived consents cannot be signed")
    signed = await _evidence(db, doc.id, "sign")
    revoked = await _evidence(db, doc.id, "revoke")
    if (purpose == "sign" and signed) or (purpose == "revoke" and (not signed or revoked)):
        raise HTTPException(409, "Consent is not eligible for this operation")
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(minutes=30)
    db.add(
        ConsentSigningLink(
            id=uuid.uuid4(),
            clinic_id=ctx.clinic_id,
            document_id=doc.id,
            token_hash=_token_hash(token),
            purpose=purpose,
            expires_at=expires,
        )
    )
    await db.flush()
    return {"data": {"token": token, "expires_at": expires.isoformat()}}


async def _link(db: AsyncSession, token: str) -> ConsentSigningLink:
    if len(token) > 128:
        raise HTTPException(404, "Link not found")
    link = (
        await db.execute(
            select(ConsentSigningLink).where(ConsentSigningLink.token_hash == _token_hash(token))
        )
    ).scalar_one_or_none()
    if not link or link.used_at or link.expires_at <= datetime.now(UTC):
        raise HTTPException(404, "Link not found or expired")
    return link


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.get("/public/consents/current")
@limiter.limit("30/minute")
async def public_consent(request: Request, response: Response, db: Db, token: Token) -> dict:
    _private(response)
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
        raise HTTPException(404, "Link not found or expired")
    patient = await PatientService.get_patient(db, link.clinic_id, doc.patient_id)
    clinic = await db.get(Clinic, link.clinic_id)
    if not patient or not clinic:
        raise HTTPException(404, "Consent not found")
    return {
        "data": {
            "title": doc.title,
            "text": doc.content["text"],
            "patient": f"{patient.first_name} {patient.last_name}",
            "clinic": clinic.name,
            "purpose": link.purpose,
        }
    }


@router.post("/public/consents/current/sign")
@limiter.limit("10/minute")
async def sign_consent(
    data: SignConsent, request: Request, response: Response, db: Db, token: Token
) -> dict:
    _private(response)
    signature = _signature_data(data.signature)
    name = data.signer_name.strip()
    if not name:
        raise HTTPException(422, "Signer name required")
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
        raise HTTPException(409, "Link is no longer valid")
    if link.purpose == "revoke" and not await _evidence(db, doc.id, "sign"):
        raise HTTPException(409, "Consent is not signed")
    patient = await PatientService.get_patient(db, link.clinic_id, doc.patient_id)
    clinic = await db.get(Clinic, link.clinic_id)
    if not patient or not clinic:
        raise HTTPException(404, "Consent not found")
    content = {
        **doc.content,
        "signature": signature,
        "signer_name": name,
        "relationship_to_patient": data.relationship_to_patient,
        "signed_at": now.isoformat(),
        "purpose": link.purpose,
    }
    snapshot = SimpleNamespace(document_type="informed_consent", content=content, title=doc.title)
    pdf = await DocumentPDFService.generate_pdf(snapshot, clinic, patient, "es")
    if not pdf.startswith(b"%PDF-"):
        raise HTTPException(500, "PDF generation failed")
    evidence_id = uuid.uuid4()
    target = _documents_root() / str(link.clinic_id) / f"consent-{evidence_id}.pdf"
    await asyncio.to_thread(_write_pdf_bytes, target, pdf)
    stored_pdf = await asyncio.to_thread(target.read_bytes)
    if stored_pdf != pdf:
        raise HTTPException(500, "Signed PDF could not be stored intact")
    db.add(
        ConsentEvidence(
            id=evidence_id,
            clinic_id=link.clinic_id,
            document_id=doc.id,
            purpose=link.purpose,
            signer_name=name,
            relationship_to_patient=data.relationship_to_patient,
            signed_at=now,
            ip_address=request.client.host[:45] if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:1000],
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


@router.get("/consents/{document_id}/evidence")
async def list_evidence(
    document_id: uuid.UUID, ctx: Ctx, _: Read, db: Db, record_access: RecordPatientAccess
) -> dict:
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
                "ip_address": e.ip_address,
                "user_agent": e.user_agent,
                "sha256": e.sha256,
            }
            for e in rows
        ]
    }


@router.get("/consents/{document_id}/evidence/{purpose}/download")
async def download_evidence(
    document_id: uuid.UUID,
    purpose: Purpose,
    ctx: Ctx,
    _: Read,
    db: Db,
    record_access: RecordPatientAccess,
) -> Response:
    doc = await _document(db, ctx.clinic_id, document_id)
    evidence = await _evidence(db, doc.id, purpose)
    if evidence is None:
        raise HTTPException(404, "Evidence not found")
    target = _documents_root() / str(ctx.clinic_id) / f"consent-{evidence.id}.pdf"
    try:
        data = await asyncio.to_thread(Path.read_bytes, target)
    except OSError:
        raise HTTPException(404, "Evidence file missing") from None
    if not secrets.compare_digest(hashlib.sha256(data).hexdigest(), evidence.sha256):
        raise HTTPException(409, "Evidence file integrity check failed")
    await record_access(doc.patient_id, "document_pdf", action="download")
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="consent-{purpose}.pdf"',
        },
    )
