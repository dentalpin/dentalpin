"""Background tasks for the integrations module."""

import logging

from app.database import async_session_maker

logger = logging.getLogger(__name__)


async def dispatch_outbox() -> None:
    """Scheduled tick: send a batch of due queued/failed webhook deliveries.

    Thin wrapper around ``WebhookGateway.dispatch_outbox`` that owns the DB
    session. Network I/O happens here (in the scheduler), never in a
    request — same shape as notifications.tasks.dispatch_outbox.
    """
    from app.modules.integrations.gateway import WebhookGateway

    try:
        async with async_session_maker() as db:
            sent = await WebhookGateway.dispatch_outbox(db)
            if sent:
                logger.debug("Webhook outbox dispatch tick processed %d delivery(ies)", sent)
    except Exception as exc:  # noqa: BLE001
        logger.error("Webhook outbox dispatch tick failed: %s", exc, exc_info=True)


async def reap_stuck_sending() -> None:
    """Scheduled job: retry deliveries left in ``sending`` by an interrupted POST."""
    from app.modules.integrations.gateway import WebhookGateway

    try:
        async with async_session_maker() as db:
            await WebhookGateway.reap_stuck_sending(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("Webhook stuck-sending reaper failed: %s", exc, exc_info=True)
