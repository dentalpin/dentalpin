"""APScheduler integration for imaging_ai background jobs.

The scheduler is owned by the host app at :mod:`app.core.scheduler`;
the module hands it the spec below via
``ImagingAiModule.get_scheduled_jobs`` (only while installed).

Jobs:

* ``imaging_ai_queue`` — every 60 s, claim queued jobs (row-locked, so
  overlapping ticks never double-run) and execute them on this worker.
  This one mechanism covers the HTTP path, the agent path (after a
  clinician confirms the proposal), and process restarts.
* ``imaging_ai_stuck_reaper`` — every 5 min, fail jobs left in
  ``running`` for >2 h (worker crash recovery; the longest runner
  timeout is 1 h, so 2 h can only mean a dead worker).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.scheduling import ScheduledJob
from app.database import async_session_maker

logger = logging.getLogger(__name__)

JOB_ID_QUEUE = "imaging_ai_queue"
JOB_ID_REAPER = "imaging_ai_stuck_reaper"

STALE_RUNNING_AFTER = timedelta(hours=2)
CLAIM_BATCH_SIZE = 5


async def process_ai_job_queue() -> None:
    """Periodic job: claim + execute queued AI jobs, clinic by clinic."""
    from .models import JOB_QUEUED, AiJob

    async with async_session_maker() as db:
        # Row-level claim: SKIP LOCKED lets an overlapping tick take the
        # next jobs instead of blocking (single-process APScheduler never
        # overlaps, but the lock makes double-execution impossible even
        # with two workers).
        rows = (
            await db.execute(
                select(AiJob)
                .where(AiJob.status == JOB_QUEUED)
                .order_by(AiJob.created_at)
                .limit(CLAIM_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
        claimed: list[tuple[UUID, UUID]] = [(j.id, j.clinic_id) for j in rows.all()]
        # Release the claim locks; execution re-locks each row itself and
        # only proceeds on status == queued, so a concurrent claimant that
        # won the same row simply no-ops (migration_import pattern).
        await db.commit()
    for job_id, clinic_id in claimed:
        from .service import AiJobService

        try:
            await AiJobService.execute_in_background(job_id, clinic_id)
        except Exception:  # noqa: BLE001 — one job must not kill the tick
            logger.exception("imaging_ai queue tick failed on job %s", job_id)


async def reap_stuck_running() -> None:
    """Periodic job: fail jobs stuck in ``running`` past the stale horizon."""
    from .models import JOB_FAILED, JOB_RUNNING, AiJob

    cutoff = datetime.now(UTC) - STALE_RUNNING_AFTER
    async with async_session_maker() as db:
        rows = (
            await db.execute(
                select(AiJob).where(AiJob.status == JOB_RUNNING, AiJob.updated_at < cutoff)
            )
        ).scalars()
        stuck = rows.all()
        for job in stuck:
            job.status = JOB_FAILED
            job.error = (
                "worker did not finish within 2h (restart or crash); re-queue the job to retry"
            )
        if stuck:
            await db.commit()
            logger.warning("imaging_ai reaped %d stuck running jobs", len(stuck))


def scheduled_jobs() -> list[ScheduledJob]:
    """Specs for :meth:`ImagingAiModule.get_scheduled_jobs`."""
    return [
        ScheduledJob(
            id=JOB_ID_QUEUE,
            func=process_ai_job_queue,
            trigger="interval",
            trigger_args={"seconds": 60},
            name="Claim and execute queued imaging AI jobs",
        ),
        ScheduledJob(
            id=JOB_ID_REAPER,
            func=reap_stuck_running,
            trigger="interval",
            trigger_args={"minutes": 5},
            name="Fail imaging AI jobs stuck in 'running'",
        ),
    ]
