"""Built-in WebPush adapter (browser push notifications).

Delivers the ``push`` channel via the Web Push protocol (``pywebpush``,
async path so one stalled push service never freezes the dispatcher):
each of the patient's active subscriptions gets ``{"title", "body"}``.
Endpoints answering 410/404 are pruned inline — dead browsers clean
themselves up with no operator action. Contract: never raises for
delivery failures, only for programmer errors.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from pywebpush import WebPushException, webpush_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import PushSubscription

from . import vapid as vapid_config
from .base import AdapterResult, Channel, OutboundMessage, SendStatus

logger = logging.getLogger(__name__)

PUSH_TTL_SECONDS = 24 * 3600
PUSH_MAX_BYTES = 4096
PUSH_TIMEOUT_SECONDS = 10.0


class PushAdapter:
    """Delivers the ``push`` channel to registered browser subscriptions."""

    channel = Channel.PUSH
    adapter_name = "webpush"

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        # No per-clinic setup: one VAPID pair per deployment. Unconfigured
        # deployments resolve no push channel (resolver skips us).
        return vapid_config.vapid_configured()

    async def send(self, db: AsyncSession, msg: OutboundMessage) -> AdapterResult:
        if msg.patient_id is None:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider="webpush",
                error_message="push needs a patient with subscriptions",
            )
        body = msg.body_text or ""
        if not body.strip():
            return AdapterResult(
                status=SendStatus.SKIPPED,
                provider="webpush",
                error_message="empty body — nothing to push",
            )
        subs = list(
            (
                await db.execute(
                    select(PushSubscription).where(
                        PushSubscription.clinic_id == msg.clinic_id,
                        PushSubscription.patient_id == msg.patient_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not subs:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider="webpush",
                error_message="patient has no push subscriptions",
            )
        payload = json.dumps({"title": msg.subject or msg.template_key, "body": body})
        payload = _fit_payload(payload)
        sent, pruned = 0, 0
        for sub in subs:
            try:
                await webpush_async(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": dict(sub.keys or {}),
                    },
                    data=payload,
                    vapid_private_key=vapid_config.vapid_private_key(),
                    vapid_claims={"sub": vapid_config.vapid_subject()},
                    ttl=PUSH_TTL_SECONDS,
                    timeout=PUSH_TIMEOUT_SECONDS,
                )
                sent += 1
            except WebPushException as exc:
                if _is_gone(exc):
                    await db.delete(sub)
                    pruned += 1
                else:
                    logger.warning("webpush send failed for %s: %s", sub.id, exc)
            except Exception as exc:  # noqa: BLE001 — per-subscription best-effort
                logger.warning("webpush send failed for %s: %s", sub.id, exc)
        await db.flush()
        if sent:
            return AdapterResult(status=SendStatus.SENT, provider="webpush")
        if pruned:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider="webpush",
                error_message="all subscriptions expired and were pruned",
            )
        return AdapterResult(
            status=SendStatus.FAILED, provider="webpush", error_message="push send failed"
        )


def _fit_payload(payload: str) -> str:
    """Cap the payload under 4 KB (push-service limit); truncate the body."""
    raw = payload.encode("utf-8")
    if len(raw) <= PUSH_MAX_BYTES:
        return payload
    data = json.loads(payload)
    overflow = len(raw) - PUSH_MAX_BYTES
    body = data.get("body", "")
    cut = max(0, len(body.encode("utf-8")) - overflow - 3)
    truncated = body.encode("utf-8")[:cut].decode("utf-8", "ignore") + "..."
    data["body"] = truncated
    return json.dumps(data)


def _is_gone(exc: WebPushException) -> bool:
    """True for push-service responses meaning 'forget this subscription'."""
    return exc.status_code in (404, 410)
