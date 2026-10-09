"""Treatment plan background tasks (APScheduler entry points).

Lives in ``treatment_plan`` rather than ``budget`` because closing a
plan is a treatment_plan write — and treatment_plan declares budget
as a dependency, so reading ``budgets`` from here respects the module
contract (ADR 0003).

Per-clinic work runs concurrently behind an ``asyncio.Semaphore``
sized below the DB pool so a slow clinic does not delay the rest.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select, text

from app.core.auth.models import Clinic
from app.database import async_session_maker

logger = logging.getLogger(__name__)

# Default plan auto-close window (days) after a budget has been
# expired. Mirrors ``DEFAULT_PLAN_AUTO_CLOSE_DAYS`` in the budget
# workflow but kept here too so the cron does not import it from
# budget (avoids tight coupling on a constant).
DEFAULT_PLAN_AUTO_CLOSE_DAYS = 30

_CLINIC_CONCURRENCY = 5


async def _close_for_clinic(
    clinic_id: UUID,
    threshold_days: int,
    today: date,
    sem: asyncio.Semaphore,
) -> None:
    from .service import TreatmentPlanService  # avoid circular at import-time

    cutoff = today - timedelta(days=threshold_days)
    async with sem, async_session_maker() as db:
        try:
            rows = (
                await db.execute(
                    text(
                        "SELECT tp.id "
                        "FROM treatment_plans tp "
                        "JOIN budgets b ON b.id = tp.budget_id "
                        "WHERE tp.clinic_id = :clinic_id "
                        "  AND tp.deleted_at IS NULL "
                        "  AND tp.status = 'pending' "
                        "  AND b.status = 'expired' "
                        "  AND b.valid_until <= :cutoff"
                    ),
                    {"clinic_id": clinic_id, "cutoff": cutoff},
                )
            ).all()

            if not rows:
                return

            for row in rows:
                plan = await TreatmentPlanService.get(db, clinic_id, row.id)
                if not plan:
                    continue
                try:
                    await TreatmentPlanService.close(
                        db,
                        clinic_id,
                        plan.id,
                        plan.created_by,
                        closure_reason="expired",
                        closure_note=(f"Auto-closed {threshold_days}d after budget expiry"),
                    )
                except ValueError as exc:
                    logger.info("auto_close_expired_plans skip plan %s: %s", plan.id, exc)
            await db.commit()
        except Exception as exc:
            logger.error(
                "auto_close_expired_plans failed for clinic %s: %s",
                clinic_id,
                exc,
                exc_info=True,
            )
            await db.rollback()


async def auto_close_expired_plans() -> None:
    """Close ``pending`` plans whose linked budget has been ``expired``
    for more than the per-clinic threshold (default: 30 days).

    Idempotent — re-runs on a clinic with no eligible plans are no-ops.
    Errors per-plan are logged but do not poison the run.
    """
    today = date.today()
    async with async_session_maker() as db:
        # ORM, not raw SQL: this used to be
        # ``text("SELECT id, settings FROM clinics WHERE deleted_at IS NULL")``
        # and `clinics` has no `deleted_at`, so the job raised
        # UndefinedColumnError on its first statement every night and no
        # plan was ever auto-closed. A column that does not exist is a test
        # failure through the mapper; in a text() string it is a 03:00 log
        # line nobody reads.
        clinic_rows = (await db.execute(select(Clinic.id, Clinic.settings))).all()

    sem = asyncio.Semaphore(_CLINIC_CONCURRENCY)
    tasks = []
    for clinic_row in clinic_rows:
        settings_json = clinic_row.settings or {}
        threshold_days = int(
            settings_json.get("plan_auto_close_days_after_expiry", DEFAULT_PLAN_AUTO_CLOSE_DAYS)
        )
        clinic_id: UUID = clinic_row.id
        tasks.append(_close_for_clinic(clinic_id, threshold_days, today, sem))

    await asyncio.gather(*tasks, return_exceptions=False)
