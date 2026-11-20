"""HTTP routes for consent templates, links and signing."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.core.patient_access import RecordPatientAccess
from app.core.pdf_locales import PDF_LOCALE_PATTERN
from app.database import get_db

from .consent_service import ConsentService
from .exceptions import ConsentRoute

router = APIRouter(route_class=ConsentRoute)
Db = Annotated[AsyncSession, Depends(get_db)]
Ctx = Annotated[ClinicContext, Depends(get_clinic_context)]
Read = Annotated[None, Depends(require_permission("documents.read"))]
Write = Annotated[None, Depends(require_permission("documents.write"))]
Purpose = Literal["sign", "revoke"]


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


def _bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(404, "Link not found or expired")
    token = authorization.removeprefix("Bearer ")
    if not token or len(token) > 128:
        raise HTTPException(404, "Link not found or expired")
    return token


Token = Annotated[str, Depends(_bearer_token)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.get("/consent-templates")
async def list_templates(ctx: Ctx, _: Read, db: Db) -> dict:
    return await ConsentService.list_templates(ctx, db)


@router.post("/consent-templates", status_code=201)
async def create_template(data: TemplateBody, ctx: Ctx, _: Write, db: Db) -> dict:
    return await ConsentService.create_template(data, ctx, db)


@router.put("/consent-templates/{template_id}")
async def update_template(
    template_id: uuid.UUID, data: TemplateBody, ctx: Ctx, _: Write, db: Db
) -> dict:
    return await ConsentService.update_template(template_id, data, ctx, db)


@router.get("/consents/signature-status")
async def consent_signature_status(
    patient_id: uuid.UUID, ctx: Ctx, _: Read, db: Db, record_access: RecordPatientAccess
) -> dict:
    return await ConsentService.consent_signature_status(patient_id, ctx, db, record_access)


@router.post("/consents", status_code=201)
async def create_consent(data: CreateConsent, ctx: Ctx, _: Write, db: Db) -> dict:
    return await ConsentService.create_consent(data, ctx, db)


@router.post("/consents/{document_id}/links", status_code=201)
async def create_link(
    document_id: uuid.UUID,
    purpose: Purpose,
    ctx: Ctx,
    _: Write,
    db: Db,
    locale: str | None = Query(default=None, pattern=PDF_LOCALE_PATTERN),
) -> dict:
    return await ConsentService.create_link(document_id, purpose, ctx, db, locale)


@router.get("/public/consents/current")
@limiter.limit("30/minute")
async def public_consent(request: Request, response: Response, db: Db, token: Token) -> dict:
    _private(response)
    return await ConsentService.public_consent(db, token)


@router.post("/public/consents/current/sign")
@limiter.limit("10/minute")
async def sign_consent(
    data: SignConsent, request: Request, response: Response, db: Db, token: Token
) -> dict:
    _private(response)
    return await ConsentService.sign_consent(
        data,
        db,
        token,
        request.client.host if request.client else None,
        request.headers.get("user-agent", ""),
    )


@router.get("/consents/{document_id}/evidence")
async def list_evidence(
    document_id: uuid.UUID, ctx: Ctx, _: Read, db: Db, record_access: RecordPatientAccess
) -> dict:
    return await ConsentService.list_evidence(document_id, ctx, db, record_access)


@router.get("/consents/{document_id}/evidence/{purpose}/download")
async def download_evidence(
    document_id: uuid.UUID,
    purpose: Purpose,
    ctx: Ctx,
    _: Read,
    db: Db,
    record_access: RecordPatientAccess,
) -> Response:
    data = await ConsentService.download_evidence(document_id, purpose, ctx, db, record_access)
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="consent-{purpose}.pdf"',
        },
    )
