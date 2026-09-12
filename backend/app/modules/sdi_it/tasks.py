"""sdi_it scheduled job: PEC send + receipt poll for every clinic on ``pec``."""

from __future__ import annotations

import logging

from app.core.scheduling import ScheduledJob
from app.database import async_session_maker

from .services import submission_queue

logger = logging.getLogger(__name__)

JOB_ID_PEC = "sdi_it_pec"


async def process_pec() -> None:
    totals = await submission_queue.process_all(async_session_maker)
    if any(totals.values()):
        logger.info("sdi_it PEC tick: %s", totals)


def scheduled_jobs() -> list[ScheduledJob]:
    return [
        ScheduledJob(
            id=JOB_ID_PEC,
            func=process_pec,
            trigger="interval",
            trigger_args={"seconds": 120},
            name="SDI (IT): send pending FPR12 files through PEC and pick up the receipts",
        )
    ]
