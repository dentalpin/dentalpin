"""Copilot service layer — conversations, messages, settings, budget."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.agents.models import Agent, AgentAuditLog
from app.core.llm.base import ContentBlock

from .models import CopilotConversation, CopilotMessage, CopilotNudge, CopilotSettings
from .serde import content_to_json

# agent_audit_logs.status values that count as a failed tool call.
_FAILED_STATUSES = ("FAILED", "BLOCKED")

_DEFAULT_MODEL_BY_PROVIDER = {
    "openai": app_settings.COPILOT_MODEL_CHAT_OPENAI,
    "anthropic": app_settings.COPILOT_MODEL_CHAT_ANTHROPIC,
}


class CopilotSettingsService:
    """Per-clinic provider/model/budget, lazy-created on first read."""

    @staticmethod
    async def get_or_create(db: AsyncSession, clinic_id: UUID) -> CopilotSettings:
        row = await db.get(CopilotSettings, clinic_id)
        if row is not None:
            return CopilotSettingsService._roll_period(row)
        row = CopilotSettings(
            clinic_id=clinic_id,
            provider=app_settings.COPILOT_PROVIDER_DEFAULT,
            model=app_settings.COPILOT_MODEL_CHAT_OPENAI,
            redaction_enabled=app_settings.COPILOT_REDACTION_DEFAULT,
            period_start=datetime.now(UTC).date().replace(day=1),
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    def _roll_period(row: CopilotSettings) -> CopilotSettings:
        """Reset monthly counters when the calendar month has changed."""
        first_of_month = datetime.now(UTC).date().replace(day=1)
        if row.period_start != first_of_month:
            row.period_start = first_of_month
            row.period_input_tokens = 0
            row.period_output_tokens = 0
            row.period_cost_cents = 0
        return row

    @staticmethod
    async def update(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict[str, Any],
        acting_user_id: UUID | None = None,
    ) -> CopilotSettings:
        row = await CopilotSettingsService.get_or_create(db, clinic_id)
        # Validate only when the caller is changing the provider; otherwise a
        # digest-only PATCH would fail on clinics whose stored provider is
        # "openai" but whose deployment has no key (the digest is no-LLM).
        if data.get("provider") == "openai" and not app_settings.OPENAI_API_KEY:
            raise ValueError("OpenAI provider selected but OPENAI_API_KEY is not configured")
        if data.get("provider") == "anthropic" and not app_settings.ANTHROPIC_API_KEY:
            raise ValueError("Anthropic provider selected but ANTHROPIC_API_KEY is not configured")
        # Switching provider without naming a model would leave the other
        # vendor's model id behind — fall back to the new provider's default.
        if (
            data.get("provider")
            and data["provider"] != row.provider
            and not data.get("model")
            and data["provider"] in _DEFAULT_MODEL_BY_PROVIDER
        ):
            data = {**data, "model": _DEFAULT_MODEL_BY_PROVIDER[data["provider"]]}
        for field in (
            "provider",
            "model",
            "redaction_enabled",
            "monthly_token_limit",
            "monthly_cost_limit_cents",
            "digest_enabled",
            "digest_hour",
        ):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])
        # Recipients (v2): a full-list replacement. ``None`` leaves it
        # unchanged; ``[]`` clears it. UUIDs are stored as strings (JSONB).
        if data.get("digest_recipient_user_ids") is not None:
            ids = [str(u) for u in data["digest_recipient_user_ids"]]
            await CopilotSettingsService._assert_clinic_members(db, clinic_id, ids)
            row.digest_recipient_user_ids = ids
        # Enabling the digest without any recipient defaults to the user
        # flipping the switch.
        if data.get("digest_enabled") and not row.digest_recipient_user_ids and acting_user_id:
            row.digest_recipient_user_ids = [str(acting_user_id)]
        await db.flush()
        return row

    @staticmethod
    async def _assert_clinic_members(
        db: AsyncSession, clinic_id: UUID, user_ids: list[str]
    ) -> None:
        """Reject recipient ids that aren't active members of the clinic.

        A digest recipient must have a clinic role — the task scopes their
        email to their effective grant set (flag-aware). Importing the core
        membership model is allowed (it's core, not another module).
        """
        if not user_ids:
            return
        from app.core.auth.models import ClinicMembership

        rows = await db.scalars(
            select(ClinicMembership.user_id).where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.user_id.in_([UUID(u) for u in user_ids]),
            )
        )
        members = {str(uid) for uid in rows}
        missing = [u for u in user_ids if u not in members]
        if missing:
            raise ValueError(f"Not clinic members: {', '.join(missing)}")


class NudgeService:
    """Proactive contextual nudges (ADR 0014 §Deferred). Clinic-scoped."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        kind: str,
        dedupe_key: str,
        payload: dict[str, Any],
        expires_at: datetime,
        required_permission: str | None = None,
    ) -> CopilotNudge | None:
        """Insert a nudge, or return None if one with the same dedupe_key
        already exists for the clinic (idempotent against event replays)."""
        existing = await db.scalar(
            select(CopilotNudge.id).where(
                CopilotNudge.clinic_id == clinic_id,
                CopilotNudge.dedupe_key == dedupe_key,
            )
        )
        if existing is not None:
            return None
        nudge = CopilotNudge(
            clinic_id=clinic_id,
            kind=kind,
            dedupe_key=dedupe_key,
            payload=payload,
            required_permission=required_permission,
            expires_at=expires_at,
        )
        db.add(nudge)
        await db.flush()
        return nudge

    @staticmethod
    async def list_active(db: AsyncSession, clinic_id: UUID, *, role: str) -> list[CopilotNudge]:
        """Pending, non-expired nudges the viewer's role is allowed to act on."""
        from app.core.auth.permissions import permission_matches
        from app.core.auth.rbac import granted_permissions_for

        granted = await granted_permissions_for(db, clinic_id, role)
        rows = (
            (
                await db.execute(
                    select(CopilotNudge)
                    .where(
                        CopilotNudge.clinic_id == clinic_id,
                        CopilotNudge.status == "pending",
                        CopilotNudge.expires_at > datetime.now(UTC),
                    )
                    .order_by(CopilotNudge.created_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        return [
            n
            for n in rows
            if n.required_permission is None
            or any(permission_matches(n.required_permission, g) for g in granted)
        ]

    @staticmethod
    async def dismiss(db: AsyncSession, clinic_id: UUID, nudge_id: UUID) -> bool:
        nudge = await db.get(CopilotNudge, nudge_id)
        if nudge is None or nudge.clinic_id != clinic_id:
            return False
        nudge.status = "dismissed"
        await db.flush()
        return True


class PendingService:
    """Read-only "Pendientes" feed (IA redesign Fase 2).

    Aggregates open work the caller can act on — overdue recalls and
    budgets awaiting a response — by calling the **same tools** the chat
    and digest use, through the registry with the caller's role
    permissions (RBAC parity by construction; ADR 0015). No new tables,
    no cross-module imports — copilot's ``depends = []`` holds. Each item
    deep-links to the owning module; the agent performs no writes here.
    """

    @staticmethod
    async def _context(db: AsyncSession, clinic_id: UUID, role: str, user_id: UUID):
        from app.core.agents.context import AgentContext, AgentMode
        from app.core.agents.models import AgentSession
        from app.core.agents.service import AgentService
        from app.core.agents.tools.registry import tool_registry
        from app.core.auth.rbac import granted_permissions_for

        from .bridge import COPILOT_GUARDRAILS

        agent = await db.scalar(
            select(Agent).where(Agent.clinic_id == clinic_id, Agent.type == "copilot").limit(1)
        )
        if agent is None:
            agent = await AgentService.create_agent(
                db, clinic_id, name="Copilot", type="copilot", mode="autonomous"
            )
        # Reuse a single per-clinic "pending" session so a drawer open
        # doesn't insert a session row every time.
        session = await db.scalar(
            select(AgentSession)
            .where(
                AgentSession.agent_id == agent.id,
                AgentSession.session_metadata.op("->>")("surface") == "copilot_pending",
            )
            .limit(1)
        )
        if session is None:
            session = await AgentService.start_session(
                db,
                agent_id=agent.id,
                clinic_id=clinic_id,
                supervisor_id=user_id,
                metadata={"surface": "copilot_pending"},
            )
        return AgentContext(
            agent_id=agent.id,
            session_id=session.id,
            clinic_id=clinic_id,
            mode=AgentMode.AUTONOMOUS,
            permissions=await granted_permissions_for(db, clinic_id, role),
            tools=tool_registry,
            db=db,
            supervisor_id=user_id,
            guardrail_config=COPILOT_GUARDRAILS,
        )

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, *, role: str, user_id: UUID
    ) -> list[dict[str, Any]]:
        from app.core.agents.tools.registry import tool_registry

        ctx = await PendingService._context(db, clinic_id, role, user_id)

        async def call(name: str, args: dict) -> dict | None:
            if name not in tool_registry.list():
                return None  # module uninstalled
            res = await tool_registry.call(ctx, name, args)
            return res.data if res.ok else None  # permission denied → omit

        items: list[dict[str, Any]] = []

        recalls = await call("recalls.list_due_recalls", {"overdue": True})
        for r in (recalls or {}).get("recalls", []):
            items.append(
                {
                    "kind": "recall",
                    "id": str(r.get("id")),
                    "patient_id": (str(r["patient_id"]) if r.get("patient_id") else None),
                    "title": r.get("patient_name"),
                    "reason": r.get("reason"),
                    "priority": r.get("priority"),
                    "link": "/recalls",
                }
            )

        budgets = await call("budget.list_budgets", {"status": ["sent"]})
        for b in (budgets or {}).get("budgets", []):
            items.append(
                {
                    "kind": "budget",
                    "id": str(b.get("id")),
                    "patient_id": (str(b["patient_id"]) if b.get("patient_id") else None),
                    "title": b.get("patient_name"),
                    "number": b.get("number"),
                    "amount": b.get("total"),
                    "link": f"/budgets/{b.get('id')}",
                }
            )

        return items


class CopilotMetricsService:
    """Read-only observability over copilot usage (issue: dashboards).

    Aggregates the existing ``agent_audit_logs`` (filtered to copilot
    agents) plus ``copilot_settings`` budget counters — no new table. All
    queries are clinic-scoped.
    """

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, *, window_days: int = 30) -> dict[str, Any]:
        window_days = min(max(window_days, 1), 365)
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        failed = AgentAuditLog.status.in_(_FAILED_STATUSES)

        def _scoped(stmt):
            return stmt.join(Agent, Agent.id == AgentAuditLog.agent_id).where(
                Agent.type == "copilot",
                AgentAuditLog.clinic_id == clinic_id,
                AgentAuditLog.created_at >= cutoff,
            )

        totals = (
            await db.execute(
                _scoped(
                    select(
                        func.count().label("total"),
                        func.count().filter(failed).label("failed"),
                        func.avg(AgentAuditLog.execution_time_ms).label("avg_ms"),
                    ).select_from(AgentAuditLog)
                )
            )
        ).one()

        tool_rows = (
            await db.execute(
                _scoped(
                    select(
                        AgentAuditLog.tool_name,
                        func.count().label("calls"),
                        func.count().filter(failed).label("errors"),
                    ).select_from(AgentAuditLog)
                )
                .group_by(AgentAuditLog.tool_name)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()

        conversations = await db.scalar(
            select(func.count())
            .select_from(CopilotConversation)
            .where(
                CopilotConversation.clinic_id == clinic_id,
                CopilotConversation.created_at >= cutoff,
            )
        )

        settings_row = await CopilotSettingsService.get_or_create(db, clinic_id)
        used = settings_row.period_input_tokens + settings_row.period_output_tokens
        limit = settings_row.monthly_token_limit
        total = int(totals.total or 0)

        return {
            "window_days": window_days,
            "total_tool_calls": total,
            "failed_tool_calls": int(totals.failed or 0),
            "error_rate": (int(totals.failed or 0) / total) if total else 0.0,
            "avg_execution_ms": int(totals.avg_ms or 0),
            "conversations": int(conversations or 0),
            "top_tools": [
                {"tool_name": r.tool_name, "calls": int(r.calls), "errors": int(r.errors)}
                for r in tool_rows
            ],
            "period_input_tokens": settings_row.period_input_tokens,
            "period_output_tokens": settings_row.period_output_tokens,
            "monthly_token_limit": limit,
            "token_usage_pct": (used / limit) if limit else None,
        }


class ConversationService:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        user_id: UUID,
        provider: str,
        model: str,
        context: dict | None = None,
        session_id: UUID | None = None,
    ) -> CopilotConversation:
        conv = CopilotConversation(
            clinic_id=clinic_id,
            user_id=user_id,
            provider=provider,
            model=model,
            context=context or {},
            session_id=session_id,
        )
        db.add(conv)
        await db.flush()
        return conv

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, conversation_id: UUID, *, user_id: UUID | None = None
    ) -> CopilotConversation | None:
        conv = await db.get(CopilotConversation, conversation_id)
        if conv is None or conv.clinic_id != clinic_id:
            return None
        if user_id is not None and conv.user_id != user_id:
            return None
        return conv

    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        user_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CopilotConversation], int]:
        page_size = min(max(page_size, 1), 100)
        conditions = [CopilotConversation.clinic_id == clinic_id]
        if user_id is not None:
            conditions.append(CopilotConversation.user_id == user_id)
        total = await db.scalar(
            select(func.count()).select_from(CopilotConversation).where(*conditions)
        )
        rows = (
            (
                await db.execute(
                    select(CopilotConversation)
                    .where(*conditions)
                    .order_by(CopilotConversation.updated_at.desc())
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total or 0)

    @staticmethod
    async def list_messages(db: AsyncSession, conversation_id: UUID) -> list[CopilotMessage]:
        rows = (
            (
                await db.execute(
                    select(CopilotMessage)
                    .where(CopilotMessage.conversation_id == conversation_id)
                    .order_by(CopilotMessage.seq.asc())
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @staticmethod
    async def _next_seq(db: AsyncSession, conversation_id: UUID) -> int:
        current = await db.scalar(
            select(func.max(CopilotMessage.seq)).where(
                CopilotMessage.conversation_id == conversation_id
            )
        )
        return int(current or 0) + 1

    @staticmethod
    async def append_message(
        db: AsyncSession,
        conv: CopilotConversation,
        *,
        role: str,
        blocks: list[ContentBlock],
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> CopilotMessage:
        msg = CopilotMessage(
            conversation_id=conv.id,
            clinic_id=conv.clinic_id,
            seq=await ConversationService._next_seq(db, conv.id),
            role=role,
            content=content_to_json(blocks),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(msg)
        await db.flush()
        return msg


class ClinicBudgetGuard:
    """BudgetGuard backed by ``copilot_settings`` monthly token counters.

    Mutates the settings + conversation rows in place; the caller commits.
    Cost accounting is token-based in v1 (cost_cents stays 0 without a
    pricing table).
    """

    def __init__(self, settings_row: CopilotSettings, conv: CopilotConversation) -> None:
        self._s = settings_row
        self._conv = conv
        self.threshold_crossed = False

    def check(self) -> bool:
        limit = self._s.monthly_token_limit
        if limit is None:
            return True
        used = self._s.period_input_tokens + self._s.period_output_tokens
        return used < limit

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self._s.period_input_tokens += input_tokens
        self._s.period_output_tokens += output_tokens
        self._conv.total_input_tokens += input_tokens
        self._conv.total_output_tokens += output_tokens
        limit = self._s.monthly_token_limit
        if limit:
            used = self._s.period_input_tokens + self._s.period_output_tokens
            if used >= int(limit * 0.8):
                self.threshold_crossed = True
