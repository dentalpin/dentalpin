"""Copilot HTTP surface — mounted at ``/api/v1/copilot/``.

Chat is streamed over SSE; everything else is ``ApiResponse``-wrapped.
The streaming endpoints resolve auth via the request context, then open
their own DB session for the duration of the stream (a request-scoped
``get_db`` session is fragile around a streaming body).
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.models import Agent, AgentSession
from app.core.agents.orchestrator import (
    BudgetExceeded,
    ConfirmationRequired,
    Final,
    Token,
    ToolCallFinished,
    ToolCallStarted,
    TurnUsage,
)
from app.core.agents.service import AgentService
from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.rbac import granted_permissions_for, has_permission_for
from app.core.events import EventType, event_bus
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import async_session_maker, get_db

from .bridge import drive_turn, resume_turn
from .schemas import (
    ConfirmRequest,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    MetricsResponse,
    NudgeResponse,
    PendingItem,
    SessionCreate,
    SettingsResponse,
    SettingsUpdate,
)
from .service import (
    ConversationService,
    CopilotMetricsService,
    CopilotSettingsService,
    NudgeService,
    PendingService,
)

router = APIRouter()


# --- SSE helpers --------------------------------------------------------


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _frame(ev) -> str | None:
    if isinstance(ev, Token):
        return _sse("token", {"text": ev.text})
    if isinstance(ev, ToolCallStarted):
        return _sse(
            "tool_call", {"call_id": ev.call_id, "name": ev.name, "arguments": ev.arguments}
        )
    if isinstance(ev, ToolCallFinished):
        return _sse(
            "tool_result",
            {"call_id": ev.call_id, "name": ev.name, "ok": ev.ok, "result": ev.result},
        )
    if isinstance(ev, ConfirmationRequired):
        return _sse(
            "confirmation_required",
            {"call_id": ev.call_id, "name": ev.name, "arguments": ev.arguments},
        )
    if isinstance(ev, TurnUsage):
        return _sse("usage", {"input_tokens": ev.input_tokens, "output_tokens": ev.output_tokens})
    if isinstance(ev, Final):
        return _sse("done", {"stop_reason": ev.stop_reason})
    if isinstance(ev, BudgetExceeded):
        return _sse("budget_exceeded", {})
    return None


async def _get_or_create_agent(db: AsyncSession, clinic_id: UUID) -> Agent:
    existing = await db.scalar(
        select(Agent).where(Agent.clinic_id == clinic_id, Agent.type == "copilot").limit(1)
    )
    if existing is not None:
        return existing
    return await AgentService.create_agent(
        db, clinic_id, name="Copilot", type="copilot", mode="autonomous"
    )


# --- Sessions -----------------------------------------------------------


@router.post("/sessions", response_model=ApiResponse[ConversationResponse], status_code=201)
async def create_session(
    body: SessionCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ConversationResponse]:
    settings_row = await CopilotSettingsService.get_or_create(db, ctx.clinic_id)
    agent = await _get_or_create_agent(db, ctx.clinic_id)
    session = await AgentService.start_session(
        db,
        agent_id=agent.id,
        clinic_id=ctx.clinic_id,
        supervisor_id=ctx.user_id,
        metadata={"surface": "copilot"},
    )
    conv = await ConversationService.create(
        db,
        clinic_id=ctx.clinic_id,
        user_id=ctx.user_id,
        provider=settings_row.provider,
        model=settings_row.model,
        context=body.context,
        session_id=session.id,
    )
    await db.commit()
    await event_bus.publish(
        EventType.COPILOT_SESSION_STARTED,
        {
            "clinic_id": str(ctx.clinic_id),
            "conversation_id": str(conv.id),
            "user_id": str(ctx.user_id),
        },
    )
    return ApiResponse(data=ConversationResponse.model_validate(conv))


@router.get("/sessions", response_model=PaginatedApiResponse[ConversationResponse])
async def list_sessions(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.history.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ConversationResponse]:
    user_filter = (
        None
        if await has_permission_for(db, ctx.clinic_id, ctx.role, "copilot.history.read_all")
        else ctx.user_id
    )
    items, total = await ConversationService.list(
        db, ctx.clinic_id, user_id=user_filter, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[ConversationResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/sessions/{conversation_id}/messages", response_model=ApiResponse[list[MessageResponse]]
)
async def list_messages(
    conversation_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.history.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[MessageResponse]]:
    user_filter = (
        None
        if await has_permission_for(db, ctx.clinic_id, ctx.role, "copilot.history.read_all")
        else ctx.user_id
    )
    conv = await ConversationService.get(db, ctx.clinic_id, conversation_id, user_id=user_filter)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    rows = await ConversationService.list_messages(db, conv.id)
    return ApiResponse(data=[MessageResponse.model_validate(m) for m in rows])


@router.post("/sessions/{conversation_id}/end", response_model=ApiResponse[ConversationResponse])
async def end_session(
    conversation_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ConversationResponse]:
    conv = await ConversationService.get(db, ctx.clinic_id, conversation_id, user_id=ctx.user_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conv.status = "ended"
    await db.commit()
    await event_bus.publish(
        EventType.COPILOT_SESSION_ENDED,
        {"clinic_id": str(ctx.clinic_id), "conversation_id": str(conv.id)},
    )
    return ApiResponse(data=ConversationResponse.model_validate(conv))


# --- Streaming chat -----------------------------------------------------


def _stream(coro_factory):
    """Wrap a bridge generator in a self-contained DB session + SSE frames."""

    async def gen():
        async with async_session_maker() as db:
            try:
                async for ev in coro_factory(db):
                    frame = _frame(ev)
                    if frame is not None:
                        yield frame
                await db.commit()
            except Exception as exc:  # surface as an SSE error, not a 500 mid-stream
                await db.rollback()
                yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")


async def _load_for_turn(db, clinic_id, conversation_id, user_id):
    conv = await ConversationService.get(db, clinic_id, conversation_id, user_id=user_id)
    if conv is None:
        return None
    settings_row = await CopilotSettingsService.get_or_create(db, clinic_id)
    agent_session = await db.get(AgentSession, conv.session_id)
    return conv, settings_row, agent_session.agent_id, conv.session_id


@router.post("/sessions/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    body: MessageCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
) -> StreamingResponse:
    clinic_id, user_id, role = ctx.clinic_id, ctx.user_id, ctx.role

    async def factory(db):
        permissions = await granted_permissions_for(db, clinic_id, role)
        loaded = await _load_for_turn(db, clinic_id, conversation_id, user_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conv, settings_row, agent_id, session_id = loaded
        async for ev in drive_turn(
            db=db,
            conv=conv,
            settings_row=settings_row,
            permissions=permissions,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            user_text=body.content,
        ):
            yield ev

    return _stream(factory)


@router.post("/sessions/{conversation_id}/confirmations/{call_id}")
async def confirm_tool(
    conversation_id: UUID,
    call_id: str,
    body: ConfirmRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
) -> StreamingResponse:
    clinic_id, user_id, role = ctx.clinic_id, ctx.user_id, ctx.role
    approve = body.decision == "confirm"

    async def factory(db):
        permissions = await granted_permissions_for(db, clinic_id, role)
        loaded = await _load_for_turn(db, clinic_id, conversation_id, user_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conv, settings_row, agent_id, session_id = loaded
        async for ev in resume_turn(
            db=db,
            conv=conv,
            settings_row=settings_row,
            permissions=permissions,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            call_id=call_id,
            approve=approve,
        ):
            yield ev

    return _stream(factory)


# --- Settings -----------------------------------------------------------


@router.get("/settings", response_model=ApiResponse[SettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SettingsResponse]:
    row = await CopilotSettingsService.get_or_create(db, ctx.clinic_id)
    await db.commit()
    return ApiResponse(data=SettingsResponse.model_validate(row))


@router.patch("/settings", response_model=ApiResponse[SettingsResponse])
async def update_settings(
    body: SettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SettingsResponse]:
    try:
        row = await CopilotSettingsService.update(
            db, ctx.clinic_id, body.model_dump(exclude_unset=True), acting_user_id=ctx.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return ApiResponse(data=SettingsResponse.model_validate(row))


@router.get("/pending", response_model=ApiResponse[list[PendingItem]])
async def list_pending(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PendingItem]]:
    items = await PendingService.get(db, ctx.clinic_id, role=ctx.role, user_id=ctx.user_id)
    await db.commit()
    return ApiResponse(data=[PendingItem.model_validate(i) for i in items])


@router.get("/nudges", response_model=ApiResponse[list[NudgeResponse]])
async def list_nudges(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[NudgeResponse]]:
    rows = await NudgeService.list_active(db, ctx.clinic_id, role=ctx.role)
    return ApiResponse(data=[NudgeResponse.model_validate(n) for n in rows])


@router.post("/nudges/{nudge_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_nudge(
    nudge_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.chat"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    ok = await NudgeService.dismiss(db, ctx.clinic_id, nudge_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Nudge not found")
    await db.commit()


@router.get("/metrics", response_model=ApiResponse[MetricsResponse])
async def get_metrics(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("copilot.supervise"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> ApiResponse[MetricsResponse]:
    data = await CopilotMetricsService.get(db, ctx.clinic_id, window_days=days)
    await db.commit()
    return ApiResponse(data=MetricsResponse.model_validate(data))
