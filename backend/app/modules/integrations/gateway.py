"""Webhook delivery gateway: enqueue + dispatch loop.

Mirrors ``notifications.gateway.NotificationGateway``'s method shapes
1:1 (see this module's ``CLAUDE.md`` "Outbox"): ``enqueue`` never
touches the network — it inserts a ``queued`` row and flushes (never
commits, leaving the decision to the caller's transaction); the
scheduled ``dispatch_outbox`` job sends with retry/backoff, batched
``FOR UPDATE SKIP LOCKED``, commit-before-network-call so no row lock
is held across I/O.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password
from app.core.webhooks.signing import SIGNATURE_HEADER, sign

from . import client as webhook_client
from .client import WebhookDeliveryError
from .models import WebhookDelivery, WebhookSubscription

logger = logging.getLogger(__name__)

_BACKOFF_CAP_SECONDS = 3600
_DISPATCH_BATCH = 50
# Issue #65 §1: auto-disable a subscription after this many consecutive
# delivery failures. CommunicationMessage has no equivalent — it tracks
# per-message terminal state, not a per-subscriber circuit breaker.
MAX_CONSECUTIVE_FAILURES = 10


def _backoff_seconds(attempts: int) -> int:
    """Exponential backoff with cap: 1m, 2m, 4m, ... <= 1h."""
    return min(60 * (2 ** max(0, attempts - 1)), _BACKOFF_CAP_SECONDS)


class WebhookGateway:
    """Owns enqueue + dispatch for webhook deliveries."""

    # ------------------------------------------------------------------ enqueue
    @staticmethod
    async def enqueue_for_event(
        db: AsyncSession,
        clinic_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: UUID | None = None,
    ) -> list[WebhookDelivery]:
        """Queue one delivery per active subscription matching ``event_type``.

        DB-only — no network I/O — so a rolled-back publisher transaction
        queues nothing, same guarantee as
        ``NotificationGateway.enqueue``.

        ``event_id`` is the stable id shared by every delivery queued for
        this one source event publish (issue #65 §1). When omitted (Phase 1
        callers / tests), a fresh id is generated once here so all matching
        deliveries still share it.
        """
        if event_id is None:
            event_id = uuid4()
        result = await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.clinic_id == clinic_id,
                WebhookSubscription.is_active.is_(True),
            )
        )
        subscriptions = [
            sub for sub in result.scalars().all() if event_type in (sub.event_types or [])
        ]

        deliveries = []
        for sub in subscriptions:
            delivery = WebhookDelivery(
                subscription_id=sub.id,
                clinic_id=clinic_id,
                event_type=event_type,
                payload=payload,
                event_id=event_id,
                status="queued",
                next_attempt_at=datetime.now(UTC),
            )
            db.add(delivery)
            deliveries.append(delivery)

        if deliveries:
            await db.flush()
        return deliveries

    # ------------------------------------------------------------------ dispatch
    @staticmethod
    async def dispatch_outbox(db: AsyncSession, limit: int = _DISPATCH_BATCH) -> int:
        """Send a batch of due queued/failed deliveries. Returns count attempted.

        Each row is locked ``FOR UPDATE SKIP LOCKED`` so concurrent dispatch
        ticks never grab the same delivery. Per-row exceptions are isolated.
        """
        now = datetime.now(UTC)
        rows = (
            (
                await db.execute(
                    select(WebhookDelivery)
                    .where(
                        WebhookDelivery.status.in_(("queued", "failed")),
                        WebhookDelivery.attempts < WebhookDelivery.max_attempts,
                        (WebhookDelivery.next_attempt_at.is_(None))
                        | (WebhookDelivery.next_attempt_at <= now),
                    )
                    .order_by(WebhookDelivery.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )

        attempted = 0
        for delivery in rows:
            attempted += 1
            try:
                await WebhookGateway._dispatch_one(db, delivery)
            except Exception as exc:  # noqa: BLE001 — isolate one poisoned row
                logger.error(
                    "webhook dispatch failed for delivery %s: %s", delivery.id, exc, exc_info=True
                )
                await db.rollback()
                await WebhookGateway._mark_failed(db, delivery, str(exc))
        return attempted

    @staticmethod
    async def _dispatch_one(db: AsyncSession, delivery: WebhookDelivery) -> None:
        subscription = await db.get(WebhookSubscription, delivery.subscription_id)
        if subscription is None or not subscription.is_active:
            await WebhookGateway._mark_failed(db, delivery, "subscription inactive or deleted")
            return

        secret = decrypt_password(subscription.secret_encrypted)
        if not secret:
            await WebhookGateway._mark_failed(db, delivery, "could not decrypt subscription secret")
            return

        delivery.status = "sending"
        delivery.attempts += 1
        # Commit before the network call so we don't hold a row lock across
        # I/O — same reasoning as NotificationGateway._dispatch_one.
        await db.commit()

        body = json.dumps(
            {
                "event": delivery.event_type,
                "event_id": str(delivery.event_id or delivery.id),
                "delivery_id": str(delivery.id),
                "data": delivery.payload,
            },
            separators=(",", ":"),
        ).encode()
        header_value = sign(secret, body)

        try:
            response = await webhook_client.post_webhook(
                subscription.target_url,
                body,
                {"Content-Type": "application/json", SIGNATURE_HEADER: header_value},
            )
        except WebhookDeliveryError as exc:
            await WebhookGateway._mark_failed(db, delivery, f"transport error: {exc}")
            await WebhookGateway._record_subscription_failure(db, subscription)
            return

        delivery.response_status_code = response.status_code
        if 200 <= response.status_code < 300:
            delivery.status = "sent"
            delivery.sent_at = datetime.now(UTC)
            delivery.error_message = None
            await db.commit()
            await WebhookGateway._record_subscription_success(db, subscription)
        else:
            await WebhookGateway._mark_failed(
                db, delivery, f"receiver returned {response.status_code}"
            )
            await WebhookGateway._record_subscription_failure(db, subscription)

    @staticmethod
    async def _mark_failed(db: AsyncSession, delivery: WebhookDelivery, error: str) -> None:
        delivery.status = "failed"
        delivery.error_message = error[:2000]
        if delivery.attempts < delivery.max_attempts:
            delivery.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=_backoff_seconds(delivery.attempts)
            )
        await db.commit()

    @staticmethod
    async def _record_subscription_success(
        db: AsyncSession, subscription: WebhookSubscription
    ) -> None:
        if subscription.consecutive_failures:
            subscription.consecutive_failures = 0
            await db.commit()

    @staticmethod
    async def _record_subscription_failure(
        db: AsyncSession, subscription: WebhookSubscription
    ) -> None:
        subscription.consecutive_failures += 1
        if subscription.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            subscription.is_active = False
            subscription.disabled_at = datetime.now(UTC)
            subscription.disabled_reason = (
                f"auto-disabled after {subscription.consecutive_failures} consecutive failures"
            )
            logger.warning(
                "webhook subscription %s auto-disabled after %d consecutive failures",
                subscription.id,
                subscription.consecutive_failures,
            )
        await db.commit()
