"""Service layer for agents, audit and approval queue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.context import AgentContext
from app.core.agents.models import (
    Agent,
    AgentApprovalQueue,
    AgentAuditLog,
    AgentSession,
)


class AgentService:
    """CRUD for agent definitions and sessions."""

    @staticmethod
    async def list_agents(db: AsyncSession, clinic_id: UUID) -> list[Agent]:
        result = await db.execute(
            select(Agent).where(Agent.clinic_id == clinic_id).order_by(Agent.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_agent(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        name: str,
        type: str,
        mode: str,
        config: dict[str, Any] | None = None,
    ) -> Agent:
        agent = Agent(
            clinic_id=clinic_id,
            name=name,
            type=type,
            mode=mode,
            config=config or {},
        )
        db.add(agent)
        await db.flush()
        return agent

    @staticmethod
    async def start_session(
        db: AsyncSession,
        *,
        agent_id: UUID,
        clinic_id: UUID,
        supervisor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSession:
        session = AgentSession(
            agent_id=agent_id,
            clinic_id=clinic_id,
            supervisor_id=supervisor_id,
            session_metadata=metadata or {},
        )
        db.add(session)
        await db.flush()
        return session

    @staticmethod
    async def list_sessions(
        db: AsyncSession, clinic_id: UUID, agent_id: UUID
    ) -> list[AgentSession]:
        result = await db.execute(
            select(AgentSession)
            .where(AgentSession.clinic_id == clinic_id, AgentSession.agent_id == agent_id)
            .order_by(AgentSession.created_at.desc())
        )
        return list(result.scalars().all())


class AuditService:
    """Append-only audit log. Every tool attempt writes one row."""

    @staticmethod
    async def record(
        ctx: AgentContext,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        status: str,
        execution_time_ms: int,
    ) -> AgentAuditLog:
        log = AgentAuditLog(
            agent_id=ctx.agent_id,
            session_id=ctx.session_id,
            clinic_id=ctx.clinic_id,
            supervisor_id=ctx.supervisor_id,
            tool_name=tool_name,
            tool_arguments=arguments,
            result=result,
            error=error,
            status=status,
            execution_time_ms=execution_time_ms,
        )
        ctx.db.add(log)
        await ctx.db.flush()
        return log

    @staticmethod
    async def list_for_clinic(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        agent_id: UUID | None = None,
        limit: int = 100,
    ) -> list[AgentAuditLog]:
        query = select(AgentAuditLog).where(AgentAuditLog.clinic_id == clinic_id)
        if agent_id is not None:
            query = query.where(AgentAuditLog.agent_id == agent_id)
        query = query.order_by(AgentAuditLog.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())


class ApprovalService:
    """Human-in-the-loop approval queue for supervised agents."""

    @staticmethod
    async def request_approval(
        ctx: AgentContext,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> AgentApprovalQueue:
        request = AgentApprovalQueue(
            id=uuid4(),
            agent_id=ctx.agent_id,
            session_id=ctx.session_id,
            clinic_id=ctx.clinic_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            status="pending",
        )
        ctx.db.add(request)
        await ctx.db.flush()
        return request

    @staticmethod
    async def list_pending(
        db: AsyncSession, clinic_id: UUID, *, status: str = "pending"
    ) -> list[AgentApprovalQueue]:
        result = await db.execute(
            select(AgentApprovalQueue)
            .where(
                AgentApprovalQueue.clinic_id == clinic_id,
                AgentApprovalQueue.status == status,
            )
            .order_by(AgentApprovalQueue.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def _decide(
        db: AsyncSession,
        clinic_id: UUID,
        request_id: UUID,
        *,
        reviewer_id: UUID,
        status: str,
        notes: str | None,
    ) -> AgentApprovalQueue | None:
        # Row lock: two reviewers (or one double click) deciding the same
        # request serialize here, and the second sees it already decided.
        # populate_existing so the status is re-read, not taken from the
        # identity map (#771).
        result = await db.execute(
            select(AgentApprovalQueue)
            .where(
                AgentApprovalQueue.id == request_id,
                AgentApprovalQueue.clinic_id == clinic_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        request = result.scalar_one_or_none()
        if request is None or request.status != "pending":
            return None
        request.status = status
        request.reviewed_by = reviewer_id
        request.reviewed_at = datetime.now(UTC)
        request.review_notes = notes
        await db.flush()
        return request

    @staticmethod
    async def approve(
        db: AsyncSession,
        clinic_id: UUID,
        request_id: UUID,
        *,
        reviewer_id: UUID,
        reviewer_role: str | None = None,
        notes: str | None = None,
    ) -> AgentApprovalQueue | None:
        """Approve a pending request and run the queued tool call.

        Status trail: ``pending`` -> ``approved`` -> ``executed`` or
        ``failed``. The call runs with the *reviewer's* permissions (``reviewer_role``;
        none if omitted, so it fails closed), re-validated against the
        tool's parameter model. Both outcomes write an audit row. A
        request already decided returns ``None`` and runs nothing, so a
        second approval can never execute the action twice.
        """
        from app.core.agents.context import AgentMode
        from app.core.agents.tools.registry import tool_registry
        from app.core.auth.rbac import granted_permissions_for

        request = await ApprovalService._decide(
            db,
            clinic_id,
            request_id,
            reviewer_id=reviewer_id,
            status="approved",
            notes=notes,
        )
        if request is None:
            return None
        # Make the decision durable before the action runs: it releases
        # the row lock, so a second approval now sees a decided request,
        # and a failing handler's rollback cannot take the decision with
        # it. If the process dies mid-run the row stays ``approved``: the
        # honest "decided, not finished" state, never run a second time.
        await db.commit()

        permissions = (
            await granted_permissions_for(db, clinic_id, reviewer_role)
            if reviewer_role is not None
            else []
        )
        ctx = AgentContext(
            agent_id=request.agent_id,
            session_id=request.session_id,
            clinic_id=clinic_id,
            mode=AgentMode.AUTONOMOUS,
            permissions=list(permissions),
            tools=tool_registry,
            db=db,
            supervisor_id=reviewer_id,
        )
        outcome = await tool_registry.execute_approved(ctx, request.tool_name, request.arguments)
        await db.refresh(request)  # a rollback after a failed run expires it
        request.status = "executed" if outcome.ok else "failed"
        await db.flush()
        return request

    @staticmethod
    async def reject(
        db: AsyncSession,
        clinic_id: UUID,
        request_id: UUID,
        *,
        reviewer_id: UUID,
        notes: str | None = None,
    ) -> AgentApprovalQueue | None:
        return await ApprovalService._decide(
            db,
            clinic_id,
            request_id,
            reviewer_id=reviewer_id,
            status="rejected",
            notes=notes,
        )
