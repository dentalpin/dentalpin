"""razorpay HTTP surface — mounted at ``/api/v1/razorpay/``.

Settings endpoints require ``razorpay.settings.*``. ``/webhook/{clinic_id}``
is PUBLIC (no JWT — auth is per-route, there is no global gate): the
``clinic_id`` path segment only selects *which secret to verify
against*; a request whose signature doesn't match that clinic's own
webhook secret is rejected before anything else runs, so a wrong or
guessed ``clinic_id`` can never forge events for a clinic whose secret
the caller doesn't know (same trust model as ``whatsapp_kapso``'s
phone-number-id resolution, adapted to Razorpay's per-account webhook
URL model).
"""

from __future__ import annotations

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.payment_gateways.service import (
    GatewayError,
    GatewayRefundService,
    PaymentRequestService,
)

from .adapter import RazorpayAdapter
from .schemas import RazorpaySettingsResponse, RazorpaySettingsUpdate
from .service import RazorpaySettingsService

logger = logging.getLogger(__name__)
router = APIRouter()


def _settings_response(settings) -> RazorpaySettingsResponse:
    return RazorpaySettingsResponse(
        mode=settings.mode if settings else "test",
        key_id=settings.key_id if settings else None,
        has_key_secret=bool(settings and settings.key_secret_encrypted),
        has_webhook_secret=bool(settings and settings.webhook_secret_encrypted),
        is_active=bool(settings and settings.is_active),
        is_verified=bool(settings and settings.is_verified),
        last_verified_at=settings.last_verified_at if settings else None,
        last_webhook_received_at=settings.last_webhook_received_at if settings else None,
        last_webhook_processed_at=settings.last_webhook_processed_at if settings else None,
        last_webhook_event_type=settings.last_webhook_event_type if settings else None,
        last_webhook_error=settings.last_webhook_error if settings else None,
        last_webhook_error_at=settings.last_webhook_error_at if settings else None,
    )


@router.get("/settings", response_model=ApiResponse[RazorpaySettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("razorpay.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RazorpaySettingsResponse]:
    settings = await RazorpaySettingsService.get_settings(db, ctx.clinic_id)
    return ApiResponse(data=_settings_response(settings))


@router.put("/settings", response_model=ApiResponse[RazorpaySettingsResponse])
async def update_settings(
    data: RazorpaySettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("razorpay.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RazorpaySettingsResponse]:
    try:
        settings = await RazorpaySettingsService.upsert_settings(
            db, ctx.clinic_id, data.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ApiResponse(data=_settings_response(settings))


# --------------------------------------------------------------------------- #
# PUBLIC webhook — no JWT. Verified by per-clinic HMAC signature.
# --------------------------------------------------------------------------- #
@router.post("/webhook/{clinic_id}")
@limiter.limit("120/minute")
async def webhook(
    clinic_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    raw = await request.body()

    settings = await RazorpaySettingsService.get_settings(db, clinic_id)
    if settings is None or not settings.webhook_secret_encrypted:
        # Unknown/unconfigured clinic — accept-and-ignore so a stale or
        # misconfigured webhook URL doesn't get retried forever, and so
        # this endpoint never confirms-by-timing whether a clinic_id is
        # a real, razorpay-configured clinic.
        return {"ok": True}

    signature = request.headers.get("X-Razorpay-Signature", "")
    if not RazorpaySettingsService.verify_signature(settings, raw, signature):
        await RazorpaySettingsService.record_webhook_error(db, settings, "invalid signature")
        # Commit now: record_webhook_error only flush()es, and get_db()
        # rolls back the whole session on ANY raised exception —
        # without this, the health bookkeeping below would vanish along
        # with the 401, leaving no trail to diagnose a misconfigured
        # webhook secret (same reasoning as payment_gateways.service's
        # pre-raise commits).
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid json")

    event_type = payload.get("event")
    await RazorpaySettingsService.record_webhook_received(db, settings, event_type)

    adapter = RazorpayAdapter()
    # Bound up front (not just inside the try) so both except branches
    # below can safely pass it to _rollback_and_record_webhook_error —
    # a payload parse_webhook_event itself rejects would otherwise leave
    # it unbound in the except blocks.
    event = None
    try:
        event = await adapter.parse_webhook_event(db, clinic_id=clinic_id, payload=payload)
        if event is not None:
            if event.event_type.startswith("refund_"):
                await _dispatch_refund_event(db, clinic_id, event)
            else:
                await _dispatch_payment_event(db, clinic_id, event)
        await RazorpaySettingsService.record_webhook_processed(db, settings)
    except GatewayError as exc:
        # A data problem (amount mismatch, illegal transition) — not
        # transient, so retries won't help; still answers 200 so
        # Razorpay stops retrying. Transactionally symmetric with the
        # Exception branch below: confirm() can flush a Payment +
        # allocations before failing later in the same call, so a plain
        # commit here would persist that half-applied confirmation
        # alongside the error record.
        logger.warning("razorpay webhook GatewayError for clinic %s: %s", clinic_id, exc)
        await _rollback_and_record_webhook_error(
            db, clinic_id=clinic_id, event=event, event_type=event_type, message=str(exc)
        )
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - transient failure: let Razorpay retry
        logger.exception("razorpay webhook processing failed for clinic %s", clinic_id)
        await _rollback_and_record_webhook_error(
            db, clinic_id=clinic_id, event=event, event_type=event_type, message=str(exc)[:500]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal error"
        )

    return {"ok": True}


async def _rollback_and_record_webhook_error(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    event,  # adapters.GatewayWebhookEvent | None — whatever this attempt got to
    event_type: str | None,
    message: str,
) -> None:
    """Roll back any partial state this webhook attempt flushed — e.g.
    ``PaymentRequestService.confirm()`` can flush a Payment + allocations
    before failing later in the same call — then record the failure
    against freshly-fetched rows. ``rollback()`` expires every ORM
    instance already loaded in this transaction (``settings``, a locked
    request/refund row), so none of them is safe to touch again; every
    row this writes to is re-fetched after the rollback.

    Also re-applies the ``raw_status_snapshot`` merge
    ``PaymentRequestService.apply_webhook_event`` makes for a
    payment-type event (``last_event_type``/``last_event_id``) — that
    write is deliberately-retained audit data (which event was rejected
    and why), not part of the failed confirmation attempt, and the
    rollback above discards it along with everything else unless it's
    redone here. Refund-type events never write that field, so there's
    nothing to restore for them.
    """
    await db.rollback()

    if (
        event is not None
        and not event.event_type.startswith("refund_")
        and event.provider_reference
    ):
        request = await PaymentRequestService.get_locked_by_provider_reference(
            db, clinic_id, "razorpay", event.provider_reference
        )
        if request is not None:
            request.raw_status_snapshot = {
                **(request.raw_status_snapshot or {}),
                "last_event_type": event.event_type,
                "last_event_id": event.provider_event_id,
            }
            await db.flush()

    fresh_settings = await RazorpaySettingsService.get_settings(db, clinic_id)
    if fresh_settings is None:
        return
    await RazorpaySettingsService.record_webhook_received(db, fresh_settings, event_type)
    await RazorpaySettingsService.record_webhook_error(db, fresh_settings, message)
    # Commit only this clean receipt/error-recording work — never a
    # failed confirmation attempt rolled back above.
    await db.commit()


async def _dispatch_payment_event(db: AsyncSession, clinic_id: UUID, event) -> None:
    if not event.provider_reference:
        return
    request = await PaymentRequestService.get_locked_by_provider_reference(
        db, clinic_id, "razorpay", event.provider_reference
    )
    if request is None:
        # Unknown request — accept and ignore. Never trust anything in
        # the payload for tenancy beyond having already verified the
        # signature against *this* clinic_id's own secret.
        return
    await PaymentRequestService.apply_webhook_event(db, request=request, event=event)


async def _dispatch_refund_event(db: AsyncSession, clinic_id: UUID, event) -> None:
    if not event.refund_provider_reference:
        return
    refund_request = await GatewayRefundService.get_locked_by_provider_reference(
        db, clinic_id, "razorpay", event.refund_provider_reference
    )
    if refund_request is None:
        return
    if event.event_type == "refund_completed":
        await GatewayRefundService.complete(db, refund_request=refund_request)
    elif event.event_type == "refund_failed":
        await GatewayRefundService.fail(
            db, refund_request=refund_request, error_message=event.error_message
        )
