"""Authenticated staff intake workflow. The signing surface is a separate change."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.events import EventType, event_bus
from app.core.patient_access import RecordPatientAccess
from app.database import get_db

from . import service
from .models import FormVersion, Intake
from .schemas import (
    AdministrativeReview,
    ClinicalReview,
    FormDefinition,
    Purpose,
    Representative,
    RetentionConfig,
)

router = APIRouter()
Ctx = Annotated[ClinicContext, Depends(get_clinic_context)]
Db = Annotated[AsyncSession, Depends(get_db)]
Configure = Annotated[None, Depends(require_permission("patient_intake.configure"))]
Issue = Annotated[None, Depends(require_permission("patient_intake.issue"))]
AdminReview = Annotated[None, Depends(require_permission("patient_intake.review_admin"))]
ClinicalReviewPermission = Annotated[
    None, Depends(require_permission("patient_intake.review_clinical"))
]
ReadHealth = Annotated[None, Depends(require_permission("patients_clinical.medical.read"))]
WriteHealth = Annotated[None, Depends(require_permission("patients_clinical.medical.write"))]
WritePatient = Annotated[None, Depends(require_permission("patients.write"))]
WriteConsent = Annotated[None, Depends(require_permission("gdpr.consents.write"))]
Withdraw = Annotated[None, Depends(require_permission("patient_intake.withdraw"))]


class IssueRequest(BaseModel):
    patient_id: UUID
    form_id: UUID
    verified_representative: Representative | None = None


def form_summary(form: FormVersion) -> dict:
    return {"id": form.id, **form.definition}


def intake_summary(intake: Intake) -> dict:
    return {
        "id": intake.id,
        "patient_id": intake.patient_id,
        "form_id": intake.form_id,
        "issued_by": intake.issued_by,
        "expires_at": intake.expires_at,
        "signed_at": intake.signed_at,
        "discarded_at": intake.discarded_at,
    }


@router.post("/forms", status_code=201)
async def publish_form(data: FormDefinition, ctx: Ctx, _: Configure, db: Db) -> dict:
    row = await service.publish_form(db, ctx.clinic_id, ctx.user_id, data)
    return {"data": form_summary(row)}


@router.get("/forms")
async def list_forms(ctx: Ctx, _: Issue, db: Db) -> dict:
    rows = await db.scalars(
        select(FormVersion)
        .where(FormVersion.clinic_id == ctx.clinic_id)
        .distinct(FormVersion.locale)
        .order_by(FormVersion.locale, FormVersion.version.desc())
    )
    return {"data": [form_summary(row) for row in rows]}


@router.put("/retention")
async def set_retention(data: RetentionConfig, ctx: Ctx, _: Configure, db: Db) -> dict:
    ctx.clinic.settings = {
        **(ctx.clinic.settings or {}),
        "patient_intake_retention": data.model_dump(),
    }
    await db.flush()
    return {"data": data}


@router.post("/intakes", status_code=201)
async def issue(data: IssueRequest, ctx: Ctx, _: Issue, db: Db) -> dict:
    row = await service.issue(
        db, ctx.clinic, data.patient_id, data.form_id, ctx.user_id, data.verified_representative
    )
    return {"data": intake_summary(row)}


async def _list_pending(
    db: Db, clinic_id: UUID, patient_id: UUID, scope: str, limit: int, offset: int
) -> list[dict]:
    column = Intake.administrative_review if scope == "administrative" else Intake.clinical_review
    rows = await db.scalars(
        select(Intake)
        .where(
            Intake.clinic_id == clinic_id,
            Intake.patient_id == patient_id,
            Intake.signed_at.is_not(None),
            Intake.discarded_at.is_(None),
            column.is_(None),
        )
        .order_by(Intake.signed_at.desc(), Intake.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [intake_summary(row) for row in rows]


@router.get("/patients/{patient_id}/pending/admin")
async def pending_admin(
    patient_id: UUID,
    ctx: Ctx,
    _: AdminReview,
    db: Db,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return {
        "data": await _list_pending(db, ctx.clinic_id, patient_id, "administrative", limit, offset)
    }


@router.get("/patients/{patient_id}/pending/clinical")
async def pending_clinical(
    patient_id: UUID,
    ctx: Ctx,
    _: ClinicalReviewPermission,
    _read: ReadHealth,
    db: Db,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return {"data": await _list_pending(db, ctx.clinic_id, patient_id, "clinical", limit, offset)}


@router.get("/intakes/{intake_id}/admin")
async def get_admin(
    intake_id: UUID,
    ctx: Ctx,
    _: AdminReview,
    db: Db,
    record_access: RecordPatientAccess,
    response: Response,
) -> dict:
    row = await service.get_intake(db, ctx.clinic_id, intake_id)
    form = await service.get_form(db, ctx.clinic_id, row.form_id)
    await record_access(row.patient_id, "patient_intake_admin")
    response.headers["Cache-Control"] = "no-store"
    answers = row.answers or {}
    return {
        "data": {
            **intake_summary(row),
            "representative": row.representative,
            "contact": answers.get("contact"),
            "choices": answers.get("choices"),
            "acknowledged_notice": answers.get("acknowledged_notice"),
            "form": {
                key: form.definition[key]
                for key in (
                    "version",
                    "locale",
                    "privacy_notice",
                    "consent_texts",
                    "enabled_channels",
                )
            },
            "review": row.administrative_review,
        }
    }


@router.get("/intakes/{intake_id}/clinical")
async def get_clinical(
    intake_id: UUID,
    ctx: Ctx,
    _: ClinicalReviewPermission,
    _read: ReadHealth,
    db: Db,
    record_access: RecordPatientAccess,
    response: Response,
) -> dict:
    row = await service.get_intake(db, ctx.clinic_id, intake_id)
    await record_access(row.patient_id, "patient_intake_clinical")
    response.headers["Cache-Control"] = "no-store"
    return {
        "data": {
            **intake_summary(row),
            "health": (row.answers or {}).get("health"),
            "review": row.clinical_review,
        }
    }


@router.post("/intakes/{intake_id}/admin", status_code=204)
async def review_admin(
    intake_id: UUID,
    data: AdministrativeReview,
    ctx: Ctx,
    _: AdminReview,
    _patient: WritePatient,
    _consent: WriteConsent,
    db: Db,
) -> None:
    await service.review_admin(db, ctx.clinic_id, intake_id, ctx.user_id, data)


@router.post("/intakes/{intake_id}/clinical", status_code=204)
async def review_clinical(
    intake_id: UUID,
    data: ClinicalReview,
    ctx: Ctx,
    _: ClinicalReviewPermission,
    _write: WriteHealth,
    db: Db,
) -> None:
    patient_id = await service.review_clinical(db, ctx.clinic_id, intake_id, ctx.user_id, data)
    if patient_id is not None:
        # The existing medical timeline subscriber opens its own session.
        await db.commit()
        await event_bus.publish(
            EventType.PATIENT_MEDICAL_UPDATED,
            {
                "patient_id": str(patient_id),
                "clinic_id": str(ctx.clinic_id),
                "user_id": str(ctx.user_id),
                "section": "history",
                "summary": "First-visit history reviewed",
            },
        )


@router.post("/intakes/{intake_id}/discard", status_code=204)
async def discard(intake_id: UUID, ctx: Ctx, _: AdminReview, db: Db) -> None:
    await service.discard(db, ctx.clinic_id, intake_id)


@router.post("/patients/{patient_id}/consents/{purpose}/withdraw", status_code=204)
async def withdraw(
    patient_id: UUID, purpose: Purpose, ctx: Ctx, _: Withdraw, _consent: WriteConsent, db: Db
) -> None:
    await service.withdraw(db, ctx.clinic_id, patient_id, ctx.user_id, purpose)
