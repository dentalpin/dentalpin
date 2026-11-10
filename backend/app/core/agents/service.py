"""Service layer for agents, audit and approval queue."""

from __future__ import annotations

from dataclasses import dataclass
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
    ApprovalStatus,
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


@dataclass(frozen=True)
class ApprovalOutcome:
    """What :meth:`ApprovalService.approve` did with a request.

    ``error`` is the tool's error when the run ended ``failed`` (``None``
    when it ``executed``). It is returned to the reviewer, not stored on
    the row; the audit log keeps it.
    """

    request: AgentApprovalQueue
    error: str | None = None


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
        db: AsyncSession, clinic_id: UUID, *, status: ApprovalStatus = "pending"
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
        status: ApprovalStatus,
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
    ) -> ApprovalOutcome | None:
        """Approve a pending request and run the queued tool call.

        Status trail: ``pending`` -> ``approved`` -> ``executed`` or
        ``failed``. Only ``executed`` and ``failed`` are end states.
        ``approved`` means *decided but never finished*: the decision was
        committed and the process stopped before the run's outcome was.
        Such a row is deliberately not retried (re-running a destructive
        call is worse than leaving it stuck); supervisors find them with
        ``GET /approvals?status=approved``. Never read ``approved`` as done.

        Two transactions. The decision (``approved``, reviewer, time,
        notes) is committed first, which also releases the row lock, so a
        second approval finds the request decided and runs nothing. The
        run and its outcome are the second: if the tool raises, its
        uncommitted work is rolled back, and the committed decision
        survives that rollback to be moved on to ``failed``.

        The call runs with the *reviewer's* permissions (``reviewer_role``;
        none if omitted, so it fails closed): the reviewer needs the
        tool's own permission as well as ``agents.supervise``. A reviewer
        without it gets ``failed`` and the request stays decided. The
        stored ``arguments`` are re-validated against the tool's
        parameter model; arguments that no longer validate end ``failed``
        without the tool being called. The approval guardrail is not
        consulted again, so the call cannot loop back into the queue;
        ``blocked_tools`` is still honoured. Every outcome writes an
        audit row.

        Returns ``None`` (and runs nothing) when the request does not
        exist in this clinic or is no longer ``pending``. Otherwise the
        :class:`ApprovalOutcome` carries the request and, on ``failed``,
        the tool's error.
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
        # Transaction 1: the decision. Committing it releases the row lock
        # and puts it out of reach of a failing handler's rollback.
        await db.commit()

        # Transaction 2: the run and its outcome.
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
        await db.commit()
        return ApprovalOutcome(request=request, error=None if outcome.ok else outcome.error)

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
