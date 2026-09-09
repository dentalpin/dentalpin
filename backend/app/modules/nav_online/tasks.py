"""nav_online scheduled jobs: submit pending records, poll sent ones."""

from __future__ import annotations

import logging

from app.core.scheduling import ScheduledJob
from app.database import async_session_maker

from .services import submission_queue

logger = logging.getLogger(__name__)

JOB_ID_SUBMISSIONS = "nav_online_submissions"


async def process_nav_submissions() -> None:
    totals = await submission_queue.process_all(async_session_maker)
    if any(totals.values()):
        logger.info("nav_online tick: %s", totals)


def scheduled_jobs() -> list[ScheduledJob]:
    return [
        ScheduledJob(
            id=JOB_ID_SUBMISSIONS,
            func=process_nav_submissions,
            trigger="interval",
            trigger_args={"seconds": 60},
            name="NAV Online Számla: send pending invoice reports and poll their status",
        )
    ]
