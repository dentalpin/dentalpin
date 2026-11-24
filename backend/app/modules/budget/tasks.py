"""Budget background tasks (APScheduler entry points).

These functions are called by ``app.core.scheduler``. Each opens its
own session and commits explicitly. They are idempotent — re-running
without state change is a no-op.

Per-clinic work runs concurrently behind an ``asyncio.Semaphore`` so
a slow clinic does not delay the rest. The cap (``_CLINIC_CONCURRENCY``)
stays comfortably under the DB pool size to avoid contention with
in-flight requests sharing the same engine.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text

from app.core.auth.models import Clinic
from app.core.utils.dates import clinic_today, clinic_zone_for
from app.database import async_session_maker

from .models import Budget, BudgetHistory
from .workflow import BudgetWorkflowService

logger = logging.getLogger(__name__)

_CLINIC_CONCURRENCY = 5


# ORM selects, not raw SQL: the old ``WHERE deleted_at IS NULL`` referenced
# a column NO migration ever created, so every cron tick raised — the
# deeper half of issue #287's "reminders are logged, nothing is sent".
# Clinics have no soft delete; there is nothing to filter.
async def _list_clinics() -> list[UUID]:
    async with async_session_maker() as db:
        rows = (await db.execute(select(Clinic.id))).all()
    return [row.id for row in rows]


async def _list_clinics_with_settings() -> list[tuple[UUID, dict, str]]:
    async with async_session_maker() as db:
        rows = (await db.execute(select(Clinic.id, Clinic.settings, Clinic.timezone))).all()
    return [(row.id, row.settings or {}, row.timezone) for row in rows]


async def _expire_for_clinic(clinic_id: UUID, sem: asyncio.Semaphore) -> None:
    async with sem, async_session_maker() as db:
        try:
            await BudgetWorkflowService.check_expired_budgets(db, clinic_id)
            await db.commit()
        except Exception as exc:
            logger.error("expire_budgets failed for clinic %s: %s", clinic_id, exc, exc_info=True)
            await db.rollback()


async def expire_budgets() -> None:
    """Mark every draft/sent budget past ``valid_until`` as ``expired``.

    Wraps ``BudgetWorkflowService.check_expired_budgets`` per clinic.
    """
    clinic_ids = await _list_clinics()
    sem = asyncio.Semaphore(_CLINIC_CONCURRENCY)
    await asyncio.gather(
        *(_expire_for_clinic(cid, sem) for cid in clinic_ids),
        return_exceptions=False,
    )


# Automatic reminders: one at each milestone, counted in clinic calendar
# days from when the quote was sent (#1115).
_REMINDER_MILESTONES = (7, 14)


def _due_milestone(today: date, sent_day: date, last_reminder_day: date | None) -> int | None:
    """The milestone to remind for today, or ``None``.

    Only the latest milestone reached counts (a cron that was down from day
    7 to day 15 sends the 14-day reminder, not both). A milestone is done
    once a reminder went out on or after its day, so it never repeats; a
    manual reminder sent after that day counts too.
    """
    days = (today - sent_day).days
    reached = [m for m in _REMINDER_MILESTONES if days >= m]
    if not reached:
        return None
    milestone = reached[-1]
    if last_reminder_day is not None and last_reminder_day >= sent_day + timedelta(days=milestone):
        return None
    return milestone


async def _send_reminders_for_clinic(clinic_id: UUID, today: date, sem: asyncio.Semaphore) -> None:
    async with sem, async_session_maker() as db:
        try:
            zone = await clinic_zone_for(db, clinic_id)
            # The send moment is the latest ``sent`` history entry. A resend
            # is a new budget version (new row), so it gets its own count.
            sent_at = (
                select(
                    BudgetHistory.budget_id,
                    func.max(BudgetHistory.changed_at).label("sent_at"),
                )
                .where(BudgetHistory.clinic_id == clinic_id, BudgetHistory.action == "sent")
                .group_by(BudgetHistory.budget_id)
                .subquery()
            )
            rows = (
                await db.execute(
                    select(Budget, sent_at.c.sent_at)
                    .outerjoin(sent_at, sent_at.c.budget_id == Budget.id)
                    .where(
                        Budget.clinic_id == clinic_id,
                        Budget.status == "sent",
                        Budget.deleted_at.is_(None),
                    )
                )
            ).all()

            for budget, sent_moment in rows:
                # A ``sent`` budget without the history entry (rows written
                # outside ``send_budget``, e.g. seeds) falls back to valid_from.
                sent_day = sent_moment.astimezone(zone).date() if sent_moment else budget.valid_from
                last = budget.last_reminder_sent_at
                last_day = last.astimezone(zone).date() if last else None
                milestone = _due_milestone(today, sent_day, last_day)
                if milestone is None:
                    continue
                await BudgetWorkflowService.send_reminder(
                    db, budget, milestone_days=milestone, automatic=True
                )
            await db.commit()
        except Exception as exc:
            logger.error(
                "send_budget_reminders failed for clinic %s: %s",
                clinic_id,
                exc,
                exc_info=True,
            )
            await db.rollback()


async def send_budget_reminders() -> None:
    """Send one reminder 7 days and one 14 days after a budget was sent.

    Honours the per-clinic toggle ``budget_reminders_enabled`` (default
    off). The function only emits the ``budget.reminder_sent`` event;
    the notifications module subscribes and queues the patient message
    through its gateway (preferred channel + fallback, issue #287).
    """
    clinics = await _list_clinics_with_settings()
    enabled = [
        (cid, timezone)
        for cid, settings_json, timezone in clinics
        if settings_json.get("budget_reminders_enabled")
    ]
    sem = asyncio.Semaphore(_CLINIC_CONCURRENCY)
    # Each clinic's own calendar: "7 days after sending" is a local date.
    await asyncio.gather(
        *(_send_reminders_for_clinic(cid, clinic_today(tz), sem) for cid, tz in enabled),
        return_exceptions=False,
    )


async def purge_budget_access_logs() -> None:
    """Drop ``budget_access_logs`` rows older than 90 days.

    Retention policy from ADR 0006. Single bulk DELETE per run.
    """
    cutoff = datetime.now(UTC) - timedelta(days=90)
    async with async_session_maker() as db:
        try:
            result = await db.execute(
                text("DELETE FROM budget_access_logs WHERE attempted_at < :cutoff"),
                {"cutoff": cutoff},
            )
            await db.commit()
            logger.info("purge_budget_access_logs: removed %s rows", result.rowcount or 0)
        except Exception as exc:
            logger.error("purge_budget_access_logs failed: %s", exc, exc_info=True)
            await db.rollback()
