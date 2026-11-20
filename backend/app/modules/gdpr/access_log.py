"""Tenant-scoped UI and CSV access to the core patient access audit."""

import csv
import io
from collections.abc import AsyncIterator
from datetime import date, datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.models import Clinic, User
from app.core.csv_safety import csv_row
from app.core.patient_access import (
    MAX_RETENTION_YEARS,
    RETENTION_SETTINGS_KEY,
    PatientAccessLog,
    retention_years,
)
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.patients.models import Patient

router = APIRouter(prefix="/access-log")
Db = Annotated[AsyncSession, Depends(get_db)]
Context = Annotated[ClinicContext, Depends(get_clinic_context)]
CanRead = Annotated[None, Depends(require_permission("gdpr.access_log.read"))]
CanChangeRetention = Annotated[None, Depends(require_permission("gdpr.retention.write"))]
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


class AccessRow(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str | None
    patient_id: UUID
    patient_name: str | None
    action: str
    resource: str
    occurred_at: datetime
    client_ip: str | None
    user_agent: str | None


class AccessUser(BaseModel):
    id: UUID
    name: str | None


class RetentionSettings(BaseModel):
    years: int = Field(ge=1, le=MAX_RETENTION_YEARS)


def access_filters(
    ctx: Context,
    patient_id: UUID | None = None,
    user_id: UUID | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list:
    if (patient_id is None) == (user_id is None):
        raise HTTPException(422, "Select exactly one patient or user")
    if (start and end and start > end) or end == date.max:
        raise HTTPException(422, "Invalid date range")

    conditions = [PatientAccessLog.clinic_id == ctx.clinic_id]
    if patient_id is not None:
        conditions.append(PatientAccessLog.patient_id == patient_id)
    else:
        conditions.append(PatientAccessLog.user_id == user_id)
    tz = ZoneInfo(ctx.clinic.timezone)
    if start is not None:
        conditions.append(PatientAccessLog.occurred_at >= datetime.combine(start, time.min, tz))
    if end is not None:
        before = datetime.combine(end + timedelta(days=1), time.min, tz)
        conditions.append(PatientAccessLog.occurred_at < before)
    return conditions


Filters = Annotated[list, Depends(access_filters)]


def access_rows(filters: list):
    return (
        select(
            PatientAccessLog, User.first_name, User.last_name, Patient.first_name, Patient.last_name
        )
        .outerjoin(User, User.id == PatientAccessLog.user_id)
        .outerjoin(
            Patient,
            and_(
                Patient.id == PatientAccessLog.patient_id,
                Patient.clinic_id == PatientAccessLog.clinic_id,
            ),
        )
        .where(*filters)
    )


def _name(first: str | None, last: str | None) -> str | None:
    return " ".join(value for value in (first, last) if value).strip() or None


def _response(row) -> AccessRow:
    entry, first, last, patient_first, patient_last = row
    return AccessRow(
        id=entry.id,
        user_id=entry.user_id,
        user_name=_name(first, last),
        patient_id=entry.patient_id,
        patient_name=_name(patient_first, patient_last),
        action=entry.action,
        resource=entry.resource,
        occurred_at=entry.occurred_at,
        client_ip=entry.client_ip,
        user_agent=entry.user_agent,
    )


@router.get("", response_model=PaginatedApiResponse[AccessRow])
async def list_access_log(
    response: Response,
    _: CanRead,
    db: Db,
    filters: Filters,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedApiResponse[AccessRow]:
    total = await db.scalar(select(func.count()).select_from(PatientAccessLog).where(*filters))
    rows = await db.execute(
        access_rows(filters)
        .order_by(PatientAccessLog.occurred_at.desc(), PatientAccessLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    response.headers.update(PRIVATE_HEADERS)
    return PaginatedApiResponse(
        data=[_response(row) for row in rows],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/users", response_model=ApiResponse[list[AccessUser]])
async def list_access_users(response: Response, ctx: Context, _: CanRead, db: Db):
    logged_users = (
        select(PatientAccessLog.user_id)
        .where(PatientAccessLog.clinic_id == ctx.clinic_id)
        .distinct()
        .subquery()
    )
    rows = await db.execute(
        select(logged_users.c.user_id, User.first_name, User.last_name)
        .outerjoin(User, User.id == logged_users.c.user_id)
        .order_by(User.last_name, User.first_name, logged_users.c.user_id)
    )
    response.headers.update(PRIVATE_HEADERS)
    return ApiResponse(
        data=[AccessUser(id=id_, name=_name(first, last)) for id_, first, last in rows]
    )


@router.get("/csv", response_class=StreamingResponse)
async def export_access_log(
    _: CanRead, db: Db, filters: Filters, start: date, end: date
) -> StreamingResponse:
    result = await db.stream(
        access_rows(filters)
        .order_by(PatientAccessLog.occurred_at.desc(), PatientAccessLog.id.desc())
        .execution_options(yield_per=500)
    )

    async def generate() -> AsyncIterator[str]:
        fields = list(AccessRow.model_fields)
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)

        def line(values: list) -> str:
            buffer.seek(0)
            buffer.truncate()
            writer.writerow(csv_row(values))
            return buffer.getvalue()

        try:
            yield "\ufeff" + line(fields)
            async for partition in result.partitions(500):
                yield "".join(
                    line(list(_response(row).model_dump(mode="json").values())) for row in partition
                )
        finally:
            await result.close()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={
            **PRIVATE_HEADERS,
            "Content-Disposition": 'attachment; filename="patient-access-log.csv"',
        },
    )


@router.get("/retention", response_model=ApiResponse[RetentionSettings])
async def get_access_retention(ctx: Context, _: CanRead) -> ApiResponse[RetentionSettings]:
    return ApiResponse(data=RetentionSettings(years=retention_years(ctx.clinic.settings)))


@router.put("/retention", response_model=ApiResponse[RetentionSettings])
async def set_access_retention(
    data: RetentionSettings, ctx: Context, _: CanRead, __: CanChangeRetention, db: Db
) -> ApiResponse[RetentionSettings]:
    current = await db.scalar(
        select(Clinic.settings).where(Clinic.id == ctx.clinic_id).with_for_update()
    )
    ctx.clinic.settings = {**(current or {}), RETENTION_SETTINGS_KEY: data.years}
    await db.commit()
    return ApiResponse(data=data)
