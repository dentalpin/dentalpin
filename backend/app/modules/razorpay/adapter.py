"""RazorpayAdapter — implements the payment_gateways ``GatewayAdapter``
contract (the only cross-module import; legal because ``payment_gateways``
is in this module's ``depends``). Pure wire + mapping: build the
Razorpay request, call the API, map the response onto neutral
dataclasses. No allocation/Payment/Refund logic — that lives entirely
in ``payment_gateways.service``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.auth.models import Clinic
from app.modules.payment_gateways.adapters import (
    GatewayCheckoutResult,
    GatewayConfirmation,
    GatewayCustomerInfo,
    GatewayRefundInitResult,
    GatewayRefundStatusResult,
    GatewayStatusResult,
    GatewayWebhookEvent,
)
from app.modules.payment_gateways.constants import GatewayRefundState, PaymentRequestState

from . import client
from .constants import (
    EVENT_ORDER_PAID,
    EVENT_PAYMENT_AUTHORIZED,
    EVENT_PAYMENT_CAPTURED,
    EVENT_PAYMENT_FAILED,
    EVENT_PAYMENT_LINK_CANCELLED,
    EVENT_PAYMENT_LINK_EXPIRED,
    EVENT_PAYMENT_LINK_PAID,
    EVENT_QR_CODE_CREDITED,
    EVENT_REFUND_FAILED,
    EVENT_REFUND_PROCESSED,
    SUPPORTED_METHODS,
    map_provider_method,
)
from .service import RazorpaySettingsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.payment_gateways.models import GatewayRefundRequest, PaymentRequest


def _epoch_to_datetime(value) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


class RazorpayAdapter:
    provider_key = "razorpay"
    supported_methods = SUPPORTED_METHODS

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        return await RazorpaySettingsService.get_active_settings(db, clinic_id) is not None

    async def _credentials(self, db: AsyncSession, clinic_id: UUID) -> tuple[str, str]:
        settings = await RazorpaySettingsService.get_active_settings(db, clinic_id)
        if settings is None:
            raise RuntimeError("razorpay is not configured or active for this clinic")
        creds = RazorpaySettingsService.decrypt_credentials(settings)
        if creds is None:
            raise RuntimeError("could not decrypt razorpay credentials")
        return creds

    async def initiate_payment(
        self,
        db: AsyncSession,
        *,
        request: PaymentRequest,
        customer: GatewayCustomerInfo,
    ) -> GatewayCheckoutResult:
        key_id, key_secret = await self._credentials(db, request.clinic_id)
        clinic = await db.get(Clinic, request.clinic_id)
        clinic_name = (clinic.name if clinic else None) or "DentalPin"
        reference_id = str(request.id)

        if request.requested_method in ("upi", "card"):
            order = await client.create_order(
                key_id,
                key_secret,
                amount=request.requested_amount,
                currency=request.currency,
                receipt=reference_id,
                notes={"payment_request_id": reference_id},
            )
            checkout_payload = {
                "key": key_id,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "name": clinic_name,
                "prefill": {
                    "name": customer.name or "",
                    "email": customer.email or "",
                    "contact": customer.phone or "",
                },
                # Hints Checkout.js to open straight on the UPI or card
                # block — the customer can still switch tabs; the
                # *confirmed* method always comes from the webhook.
                "method": {"upi": True} if request.requested_method == "upi" else {"card": True},
            }
            return GatewayCheckoutResult(
                provider_reference=order["id"],
                method=request.requested_method,
                checkout_payload=checkout_payload,
                raw_provider_status=order.get("status"),
            )

        if request.requested_method == "qr":
            qr = await client.create_qr_code(
                key_id,
                key_secret,
                amount=request.requested_amount,
                description=f"{clinic_name} payment",
                reference_id=reference_id,
            )
            return GatewayCheckoutResult(
                provider_reference=qr["id"],
                method="qr",
                qr_image_url=qr.get("image_url"),
                raw_provider_status=qr.get("status"),
            )

        if request.requested_method == "payment_link":
            customer_payload: dict = {}
            if customer.name:
                customer_payload["name"] = customer.name
            if customer.email:
                customer_payload["email"] = customer.email
            if customer.phone:
                customer_payload["contact"] = customer.phone
            link = await client.create_payment_link(
                key_id,
                key_secret,
                amount=request.requested_amount,
                currency=request.currency,
                description=f"{clinic_name} payment",
                reference_id=reference_id,
                customer=customer_payload or None,
            )
            return GatewayCheckoutResult(
                provider_reference=link["id"],
                method="payment_link",
                redirect_url=link.get("short_url"),
                raw_provider_status=link.get("status"),
            )

        raise RuntimeError(f"razorpay does not support method {request.requested_method!r}")

    async def verify_payment_status(
        self, db: AsyncSession, *, request: PaymentRequest
    ) -> GatewayStatusResult:
        """Best-effort on-demand pull for a manual refresh. The webhook
        remains authoritative — any parsing ambiguity here resolves to
        "no change" (state stays whatever the request already is)
        rather than guessing.
        """
        if not request.provider_reference:
            return GatewayStatusResult(state=request.state)
        try:
            key_id, key_secret = await self._credentials(db, request.clinic_id)
            payments: list[dict] = []
            if request.requested_method in ("upi", "card"):
                payments = await client.list_order_payments(
                    key_id, key_secret, request.provider_reference
                )
            elif request.requested_method == "qr":
                payments = await client.list_qr_code_payments(
                    key_id, key_secret, request.provider_reference
                )
            elif request.requested_method == "payment_link":
                link = await client.fetch_payment_link(
                    key_id, key_secret, request.provider_reference
                )
                if link.get("status") == "expired":
                    return GatewayStatusResult(state=str(PaymentRequestState.EXPIRED))
                if link.get("status") == "cancelled":
                    return GatewayStatusResult(state=str(PaymentRequestState.CANCELLED))
                payments = link.get("payments") or []

            captured = next((p for p in payments if p.get("status") == "captured"), None)
            if captured is not None:
                confirmation = GatewayConfirmation(
                    provider_payment_reference=captured["id"],
                    confirmed_method=map_provider_method(captured.get("method")),
                    amount=client.from_paise(int(captured.get("amount", 0))),
                    currency=captured.get("currency", request.currency),
                    captured_at=_epoch_to_datetime(captured.get("created_at")),
                )
                return GatewayStatusResult(
                    state=str(PaymentRequestState.SUCCEEDED), confirmation=confirmation
                )
        except Exception as exc:  # noqa: BLE001 - defensive: a refresh must never 500 the UI
            return GatewayStatusResult(state=request.state, error_message=str(exc)[:300])
        return GatewayStatusResult(state=request.state)

    def verify_webhook_signature(
        self, *, raw_body: bytes, headers: dict[str, str], secret: str
    ) -> bool:
        import hashlib
        import hmac

        signature = headers.get("x-razorpay-signature", "")
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    async def parse_webhook_event(
        self, db: AsyncSession, *, clinic_id: UUID, payload: dict
    ) -> GatewayWebhookEvent | None:
        event = payload.get("event")
        contains = payload.get("payload") or {}
        payment_entity = ((contains.get("payment") or {}).get("entity")) or {}
        order_entity = ((contains.get("order") or {}).get("entity")) or {}
        refund_entity = ((contains.get("refund") or {}).get("entity")) or {}
        link_entity = ((contains.get("payment_link") or {}).get("entity")) or {}
        qr_entity = ((contains.get("qr_code") or {}).get("entity")) or {}

        def _confirmation_from_payment(entity: dict) -> GatewayConfirmation | None:
            if not entity.get("id"):
                return None
            return GatewayConfirmation(
                provider_payment_reference=entity["id"],
                confirmed_method=map_provider_method(entity.get("method")),
                amount=client.from_paise(int(entity.get("amount", 0))),
                currency=entity.get("currency", "INR"),
                captured_at=_epoch_to_datetime(entity.get("created_at")),
            )

        if event in (EVENT_PAYMENT_CAPTURED, EVENT_ORDER_PAID):
            provider_reference = payment_entity.get("order_id") or order_entity.get("id")
            confirmation = _confirmation_from_payment(payment_entity)
            if not provider_reference or confirmation is None:
                return None
            return GatewayWebhookEvent(
                event_type="payment_succeeded",
                provider_reference=provider_reference,
                provider_event_id=payment_entity.get("id"),
                confirmation=confirmation,
            )

        if event == EVENT_PAYMENT_LINK_PAID:
            provider_reference = link_entity.get("id")
            confirmation = _confirmation_from_payment(payment_entity)
            if not provider_reference or confirmation is None:
                return None
            return GatewayWebhookEvent(
                event_type="payment_succeeded",
                provider_reference=provider_reference,
                provider_event_id=payment_entity.get("id"),
                confirmation=confirmation,
            )

        if event == EVENT_QR_CODE_CREDITED:
            provider_reference = qr_entity.get("id")
            confirmation = _confirmation_from_payment(payment_entity)
            if not provider_reference or confirmation is None:
                return None
            return GatewayWebhookEvent(
                event_type="payment_succeeded",
                provider_reference=provider_reference,
                provider_event_id=payment_entity.get("id"),
                confirmation=confirmation,
            )

        if event == EVENT_PAYMENT_AUTHORIZED:
            # payment_capture=1 (auto-capture) is always set at order
            # creation (see client.create_order) — an authorized-but-
            # not-captured event is transient; payment.captured follows
            # immediately, so nothing to do here.
            if payment_entity.get("captured"):
                return None
            provider_reference = payment_entity.get("order_id")
            if not provider_reference:
                return None
            return GatewayWebhookEvent(
                event_type="payment_authorized",
                provider_reference=provider_reference,
                provider_event_id=payment_entity.get("id"),
            )

        if event == EVENT_PAYMENT_FAILED:
            provider_reference = payment_entity.get("order_id")
            if not provider_reference:
                return None
            return GatewayWebhookEvent(
                event_type="payment_failed",
                provider_reference=provider_reference,
                provider_event_id=payment_entity.get("id"),
                error_code=payment_entity.get("error_code"),
                error_message=payment_entity.get("error_description"),
            )

        if event == EVENT_PAYMENT_LINK_EXPIRED:
            provider_reference = link_entity.get("id")
            if not provider_reference:
                return None
            return GatewayWebhookEvent(
                event_type="payment_expired", provider_reference=provider_reference
            )

        if event == EVENT_PAYMENT_LINK_CANCELLED:
            provider_reference = link_entity.get("id")
            if not provider_reference:
                return None
            return GatewayWebhookEvent(
                event_type="payment_cancelled", provider_reference=provider_reference
            )

        if event == EVENT_REFUND_PROCESSED:
            refund_id = refund_entity.get("id")
            if not refund_id:
                return None
            return GatewayWebhookEvent(
                event_type="refund_completed",
                refund_provider_reference=refund_id,
                provider_event_id=refund_id,
            )

        if event == EVENT_REFUND_FAILED:
            refund_id = refund_entity.get("id")
            if not refund_id:
                return None
            return GatewayWebhookEvent(
                event_type="refund_failed",
                refund_provider_reference=refund_id,
                provider_event_id=refund_id,
                error_message=refund_entity.get("error_description") or refund_entity.get("status"),
            )

        # A real event this adapter has nothing to do with — accept and
        # ignore rather than error, so Razorpay doesn't retry forever.
        return None

    async def initiate_refund(
        self, db: AsyncSession, *, refund_request: GatewayRefundRequest
    ) -> GatewayRefundInitResult:
        try:
            key_id, key_secret = await self._credentials(db, refund_request.clinic_id)
            result = await client.create_refund(
                key_id,
                key_secret,
                payment_id=refund_request.provider_payment_reference,
                amount=refund_request.requested_amount,
                receipt=str(refund_request.id),
                notes={"reason_code": refund_request.reason_code},
            )
        except Exception as exc:  # noqa: BLE001 - transport/programmer error, surfaced to the caller
            return GatewayRefundInitResult(
                provider_refund_reference=None,
                state=str(GatewayRefundState.FAILED),
                error_message=str(exc)[:500],
            )

        status = result.get("status")
        # Razorpay resolves most refunds synchronously in the API
        # response ("processed"); bank-transfer-backed refunds can come
        # back "pending"/"processing" and only resolve via the
        # refund.processed / refund.failed webhook later.
        state = (
            str(GatewayRefundState.COMPLETED)
            if status == "processed"
            else str(GatewayRefundState.PROCESSING)
        )
        return GatewayRefundInitResult(provider_refund_reference=result.get("id"), state=state)

    async def refresh_refund_status(
        self, db: AsyncSession, *, refund_request: GatewayRefundRequest
    ) -> GatewayRefundStatusResult:
        if not refund_request.provider_refund_reference:
            return GatewayRefundStatusResult(state=refund_request.state)
        try:
            key_id, key_secret = await self._credentials(db, refund_request.clinic_id)
            result = await client.fetch_refund(
                key_id,
                key_secret,
                payment_id=refund_request.provider_payment_reference,
                refund_id=refund_request.provider_refund_reference,
            )
        except Exception as exc:  # noqa: BLE001 - defensive: a refresh must never 500 the UI
            return GatewayRefundStatusResult(
                state=refund_request.state, error_message=str(exc)[:300]
            )

        status = result.get("status")
        if status == "processed":
            return GatewayRefundStatusResult(state=str(GatewayRefundState.COMPLETED))
        if status == "failed":
            return GatewayRefundStatusResult(state=str(GatewayRefundState.FAILED))
        return GatewayRefundStatusResult(state=refund_request.state)
