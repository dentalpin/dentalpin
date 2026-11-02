"""FastAPI endpoints for agent management, approval queue and audit log."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentSessionResponse,
    ApprovalDecision,
    ApprovalResponse,
    AuditLogResponse,
)
from app.core.agents.service import AgentService, ApprovalService, AuditService
from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


# --- Agents (definitions) --------------------------------------------------


@router.get("", response_model=PaginatedApiResponse[AgentResponse])
async def list_agents(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[AgentResponse]:
    agents = await AgentService.list_agents(db, ctx.clinic_id)
    data = [AgentResponse.model_validate(a) for a in agents]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=len(data) or 1)


@router.post(
    "",
    response_model=ApiResponse[AgentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    payload: AgentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AgentResponse]:
    agent = await AgentService.create_agent(
        db,
        ctx.clinic_id,
        name=payload.name,
        type=payload.type,
        mode=payload.mode,
        config=payload.config,
    )
    return ApiResponse(data=AgentResponse.model_validate(agent))


@router.get(
    "/{agent_id}/sessions",
    response_model=PaginatedApiResponse[AgentSessionResponse],
)
async def list_agent_sessions(
    agent_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[AgentSessionResponse]:
    sessions = await AgentService.list_sessions(db, ctx.clinic_id, agent_id)
    data = [AgentSessionResponse.model_validate(s) for s in sessions]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=len(data) or 1)


# --- Approval queue --------------------------------------------------------


@router.get("/approvals", response_model=PaginatedApiResponse[ApprovalResponse])
async def list_approvals(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.supervise"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str = Query(default="pending", alias="status"),
) -> PaginatedApiResponse[ApprovalResponse]:
    items = await ApprovalService.list_pending(db, ctx.clinic_id, status=status_filter)
    data = [ApprovalResponse.model_validate(i) for i in items]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=len(data) or 1)


@router.post(
    "/approvals/{request_id}/approve",
    response_model=ApiResponse[ApprovalResponse],
)
async def approve_request(
    request_id: UUID,
    payload: ApprovalDecision,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.supervise"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ApprovalResponse]:
    request = await ApprovalService.approve(
        db,
        ctx.clinic_id,
        request_id,
        reviewer_id=ctx.user_id,
        reviewer_role=ctx.role,
        notes=payload.notes,
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found or not pending")
    return ApiResponse(data=ApprovalResponse.model_validate(request))


@router.post(
    "/approvals/{request_id}/reject",
    response_model=ApiResponse[ApprovalResponse],
)
async def reject_request(
    request_id: UUID,
    payload: ApprovalDecision,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.supervise"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ApprovalResponse]:
    request = await ApprovalService.reject(
        db, ctx.clinic_id, request_id, reviewer_id=ctx.user_id, notes=payload.notes
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found or not pending")
    return ApiResponse(data=ApprovalResponse.model_validate(request))


# --- Audit log -------------------------------------------------------------


@router.get("/audit", response_model=PaginatedApiResponse[AuditLogResponse])
async def list_audit(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agents.view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    agent_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> PaginatedApiResponse[AuditLogResponse]:
    logs = await AuditService.list_for_clinic(db, ctx.clinic_id, agent_id=agent_id, limit=limit)
    data = [AuditLogResponse.model_validate(log) for log in logs]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=len(data) or 1)
