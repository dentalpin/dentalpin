"""Copilot background tasks (APScheduler entry points).

Morning digest (proactivity v1): a deterministic — no LLM — daily email
per opted-in clinic summarising today's agenda, overdue recalls and
budgets awaiting response. Data is gathered **through the tool
registry** with the recipient's real role permissions, so RBAC parity
holds mechanically and no cross-module import is needed (same
chokepoint the chat bridge uses). Tools the recipient can't call (or
whose module is uninstalled) are silently omitted from the digest.

Follows ``budget/tasks.py``: one session per clinic behind a semaphore;
idempotent (re-running just sends another email — the cron fires once
per hour and matches ``digest_hour`` against the server-local hour).

See ``docs/technical/copilot/proactivity.md`` + the ADR for the design
decisions (delivery channel, timezone caveat, deferred nudges).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.context import AgentContext, AgentMode
from app.core.agents.service import AgentService
from app.core.agents.tools.registry import tool_registry
from app.core.auth.models import ClinicMembership, User
from app.core.auth.permissions import get_role_permissions
from app.core.email.service import EmailService
from app.core.events import event_bus
from app.core.events.types import EventType
from app.database import async_session_maker

from .bridge import COPILOT_GUARDRAILS
from .models import CopilotSettings

logger = logging.getLogger(__name__)

_CLINIC_CONCURRENCY = 5

_SUBJECT = {
    "es": "Briefing del día — {clinic_name}",
    "en": "Daily briefing — {clinic_name}",
}


async def _clinic_locale(db: AsyncSession, clinic_id: UUID) -> str:
    # Same lookup as notifications.resolve_clinic_communication_locale,
    # inlined to keep copilot's depends = [] (notifications is a module).
    row = (
        await db.execute(text("SELECT settings FROM clinics WHERE id = :id"), {"id": clinic_id})
    ).first()
    settings = (row.settings or {}) if row else {}
    lang = settings.get("communication_language") if isinstance(settings, dict) else None
    return lang or "es"


async def _clinic_name(db: AsyncSession, clinic_id: UUID) -> str:
    name = await db.scalar(text("SELECT name FROM clinics WHERE id = :id"), {"id": clinic_id})
    return name or "Denplant"


async def _clinic_tz(db: AsyncSession, clinic_id: UUID) -> ZoneInfo:
    """Clinic IANA timezone (``clinics.timezone``), UTC on miss."""
    name = await db.scalar(text("SELECT timezone FROM clinics WHERE id = :id"), {"id": clinic_id})
    try:
        return ZoneInfo(name) if name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


async def _digest_context(
    db: AsyncSession, clinic_id: UUID, user_id: UUID, today: date
) -> dict | None:
    """Gather digest data for one recipient via the registry, scoped to
    that recipient's role permissions, or None when undeliverable."""
    user = await db.get(User, user_id)
    if user is None or not user.is_active or not user.email:
        return None
    role = await db.scalar(
        select(ClinicMembership.role).where(
            ClinicMembership.user_id == user.id,
            ClinicMembership.clinic_id == clinic_id,
        )
    )
    if role is None:
        return None

    agent = await AgentService.create_agent(
        db, clinic_id, name="Copilot digest", type="copilot", mode="autonomous"
    )
    session = await AgentService.start_session(
        db,
        agent_id=agent.id,
        clinic_id=clinic_id,
        supervisor_id=user.id,
        metadata={"surface": "copilot_digest"},
    )
    ctx = AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic_id,
        mode=AgentMode.AUTONOMOUS,
        permissions=get_role_permissions(role),
        tools=tool_registry,
        db=db,
        supervisor_id=user.id,
        guardrail_config=COPILOT_GUARDRAILS,
    )

    async def call(name: str, args: dict) -> dict[str, Any] | None:
        if name not in tool_registry.list():
            return None  # module uninstalled
        res = await tool_registry.call(ctx, name, args)
        return res.data if res.ok else None  # permission denied → omit section

    overview = await call("agenda.get_day_overview", {"date": today.isoformat()})
    recalls = await call("recalls.list_due_recalls", {"overdue": True})
    budgets = await call("budget.list_budgets", {"status": ["sent"]})
    if overview is None and recalls is None and budgets is None:
        return None

    return {
        "recipient": user,
        "today": today.strftime("%d/%m/%Y"),
        "appointments": (overview or {}).get("appointments"),
        "recalls": (recalls or {}).get("recalls"),
        "budgets": (budgets or {}).get("budgets"),
    }


async def _send_for_clinic(clinic_id: UUID, today: date, sem: asyncio.Semaphore) -> None:
    async with sem, async_session_maker() as db:
        try:
            row = await db.get(CopilotSettings, clinic_id)
            if row is None or not row.digest_enabled or not row.digest_recipient_user_ids:
                return
            locale = await _clinic_locale(db, clinic_id)
            clinic_name = await _clinic_name(db, clinic_id)
            subject = _SUBJECT.get(locale, _SUBJECT["es"]).format(clinic_name=clinic_name)
            # One email per recipient, each scoped to that recipient's role.
            for raw_id in row.digest_recipient_user_ids:
                try:
                    user_id = UUID(str(raw_id))
                except (ValueError, TypeError):
                    continue
                context = await _digest_context(db, clinic_id, user_id, today)
                if context is None:
                    logger.info(
                        "copilot digest: clinic %s recipient %s undeliverable, skipped",
                        clinic_id,
                        raw_id,
                    )
                    continue
                recipient: User = context.pop("recipient")
                result = await EmailService().send_templated(
                    to_email=recipient.email,
                    to_name=f"{recipient.first_name} {recipient.last_name}",
                    template_key="copilot_morning_digest",
                    subject=subject,
                    locale=locale,
                    context={**context, "clinic_name": clinic_name},
                    db=db,
                    clinic_id=clinic_id,
                )
                await db.commit()
                await event_bus.publish(
                    EventType.COPILOT_DIGEST_SENT,
                    {
                        "clinic_id": str(clinic_id),
                        "recipient_user_id": str(recipient.id),
                        "date": today.isoformat(),
                        "email_status": result.status.value,
                    },
                )
        except Exception as exc:
            logger.error("copilot digest failed for clinic %s: %s", clinic_id, exc, exc_info=True)
            await db.rollback()


async def send_morning_digests(now: datetime | None = None) -> None:
    """Hourly entry point: send the digest to clinics whose ``digest_hour``
    matches the current hour **in the clinic's own timezone** (v2). The
    "today" passed to each clinic is its local date, too."""
    now_utc = now or datetime.now(UTC)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    async with async_session_maker() as db:
        rows = (
            await db.execute(
                select(CopilotSettings.clinic_id, CopilotSettings.digest_hour).where(
                    CopilotSettings.digest_enabled.is_(True)
                )
            )
        ).all()
        due: list[tuple[UUID, date]] = []
        for clinic_id, digest_hour in rows:
            local_now = now_utc.astimezone(await _clinic_tz(db, clinic_id))
            if local_now.hour == digest_hour:
                due.append((clinic_id, local_now.date()))
    if not due:
        return
    sem = asyncio.Semaphore(_CLINIC_CONCURRENCY)
    await asyncio.gather(
        *(_send_for_clinic(cid, today, sem) for cid, today in due),
        return_exceptions=False,
    )
