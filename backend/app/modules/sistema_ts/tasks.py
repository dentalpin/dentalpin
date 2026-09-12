"""sistema_ts scheduled job: sync new documents and send pending ones."""

from __future__ import annotations

import logging

from app.core.scheduling import ScheduledJob
from app.database import async_session_maker

from .services import submission_queue

logger = logging.getLogger(__name__)

JOB_ID = "sistema_ts_submissions"


async def process_sistema_ts() -> None:
    totals = await submission_queue.process_all(async_session_maker)
    if any(totals.values()):
        logger.info("sistema_ts tick: %s", totals)


def scheduled_jobs() -> list[ScheduledJob]:
    return [
        ScheduledJob(
            id=JOB_ID,
            func=process_sistema_ts,
            trigger="interval",
            trigger_args={"seconds": 120},
            name="Sistema Tessera Sanitaria: send paid patient invoices and their refunds",
        )
    ]
