"""Agent tools for the gdpr module. Thin wrappers over the GDPR services."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import ConsentCreate, GdprRequestCreate, RetentionPolicyCreate
from .service import ConsentService, ErasureService, GdprService, RetentionService


class CreateRequestArgs(BaseModel):
    requester_name: str
    requester_email: str
    request_type: str = Field(description="access|rectification|erasure|portability|restrict")
    patient_id: str | None = None
    notes: str | None = None


class ListRequestsArgs(BaseModel):
    status: str | None = None
    request_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class RecordConsentArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    purpose: str = Field(description="e.g. sms, email, third_party_sharing")
    granted: bool = True
    provided_text: str | None = None


class ListConsentsArgs(BaseModel):
    patient_id: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CreatePolicyArgs(BaseModel):
    data_category: str = Field(description="e.g. clinical, billing, radiology")
    retention_years: int = Field(ge=0)


class ExecuteErasureArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    categories: list[str] = Field(description="data categories to erase")
    rationale: str | None = None


async def _create_request(ctx: AgentContext, params: CreateRequestArgs) -> dict:
    row = await GdprService.create_request(
        ctx.db,
        ctx.clinic_id,
        GdprRequestCreate(
            requester_name=params.requester_name,
            requester_email=params.requester_email,
            request_type=params.request_type,
            patient_id=params.patient_id,
            notes=params.notes,
        ),
    )
    return {
        "id": row.id,
        "status": row.status,
        "request_type": row.request_type,
        "deadline_at": row.deadline_at,
    }


async def _list_requests(ctx: AgentContext, params: ListRequestsArgs) -> dict:
    items, total = await GdprService.list_requests(
        ctx.db,
        ctx.clinic_id,
        status=params.status,
        request_type=params.request_type,
        page=1,
        page_size=params.limit,
    )
    return {
        "total": total,
        "requests": [
            {
                "id": r.id,
                "request_type": r.request_type,
                "status": r.status,
                "patient_id": r.patient_id,
            }
            for r in items
        ],
    }


async def _record_consent(ctx: AgentContext, params: RecordConsentArgs) -> dict:
    row = await ConsentService.grant_or_withdraw(
        ctx.db,
        ctx.clinic_id,
        ConsentCreate(
            patient_id=params.patient_id,
            purpose=params.purpose,
            granted=params.granted,
            provided_text=params.provided_text,
        ),
    )
    return {
        "id": row.id,
        "patient_id": row.patient_id,
        "purpose": row.purpose,
        "granted": row.granted,
        "granted_at": row.granted_at,
        "withdrawn_at": row.withdrawn_at,
    }


async def _list_consents(ctx: AgentContext, params: ListConsentsArgs) -> dict:
    items, total = await ConsentService.list_consents(
        ctx.db,
        ctx.clinic_id,
        patient_id=UUID(params.patient_id) if params.patient_id else None,
        page=1,
        page_size=params.limit,
    )
    return {
        "total": total,
        "consents": [
            {"id": c.id, "patient_id": c.patient_id, "purpose": c.purpose, "granted": c.granted}
            for c in items
        ],
    }


async def _create_policy(ctx: AgentContext, params: CreatePolicyArgs) -> dict:
    row = await RetentionService.create(
        ctx.db,
        ctx.clinic_id,
        RetentionPolicyCreate(
            data_category=params.data_category, retention_years=params.retention_years
        ),
    )
    return {
        "id": row.id,
        "data_category": row.data_category,
        "retention_years": row.retention_years,
    }


async def _execute_erasure(ctx: AgentContext, params: ExecuteErasureArgs) -> dict:
    result = await ErasureService.execute(
        ctx.db,
        ctx.clinic_id,
        patient_id=UUID(params.patient_id),
        categories=params.categories,
        rationale=params.rationale,
        executed_by=ctx.agent_id,
    )
    return {
        "patient_id": result.patient_id,
        "erased_categories": result.erased_categories,
        "retained_categories": result.retained_categories,
        "audit_log_id": result.audit_log_id,
    }


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="create_gdpr_request",
            description="Log a data-subject request (access/rectification/erasure/portability/restrict)",
            category=ToolCategory.WRITE,
            permissions=["gdpr.requests.write"],
            handler=_create_request,
            parameters=CreateRequestArgs,
        ),
        Tool(
            name="list_gdpr_requests",
            description="List data-subject requests, optionally by status or type",
            category=ToolCategory.READ,
            permissions=["gdpr.requests.read"],
            handler=_list_requests,
            parameters=ListRequestsArgs,
        ),
        Tool(
            name="record_gdpr_consent",
            description="Record or withdraw a patient consent for a processing purpose",
            category=ToolCategory.WRITE,
            permissions=["gdpr.consents.write"],
            handler=_record_consent,
            parameters=RecordConsentArgs,
        ),
        Tool(
            name="list_gdpr_consents",
            description="List a patient's consent records",
            category=ToolCategory.READ,
            permissions=["gdpr.consents.read"],
            handler=_list_consents,
            parameters=ListConsentsArgs,
        ),
        Tool(
            name="create_retention_policy",
            description="Create a retention policy that gates erasure eligibility",
            category=ToolCategory.WRITE,
            permissions=["gdpr.retention.write"],
            handler=_create_policy,
            parameters=CreatePolicyArgs,
        ),
        Tool(
            name="execute_partial_erasure",
            description=(
                "Partially erase a patient's PII once retention allows "
                "(blanking identity fields, never hard-deleting the row)"
            ),
            category=ToolCategory.DESTRUCTIVE,
            permissions=["gdpr.requests.write"],
            handler=_execute_erasure,
            parameters=ExecuteErasureArgs,
        ),
    ]
