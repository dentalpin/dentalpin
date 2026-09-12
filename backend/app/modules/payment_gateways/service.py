"""payment_gateways business logic.

``PaymentRequestService`` owns the pre-payment lifecycle and is the
*only* code path allowed to create a core ``payments.Payment`` from a
gateway confirmation. ``GatewayRefundService`` mirrors that for
refunds. Both delegate the actual financial write to
``payments.workflow`` — this module never constructs a ``Payment`` or
``Refund`` row itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.patients.models import Patient
from app.modules.payments.models import Payment, Refund
from app.modules.payments.service import PaymentService
from app.modules.payments.workflow import PaymentWorkflowError, record_payment, refund_payment

from .adapters import GatewayCustomerInfo, GatewayWebhookEvent, gateway_registry
from .constants import (
    TERMINAL_REFUND_STATES,
    TERMINAL_REQUEST_STATES,
    GatewayRefundState,
    PaymentRequestState,
    validate_payment_request_transition,
    validate_refund_transition,
)
from .models import GatewayRefundRequest, PaymentRequest


class GatewayError(ValueError):
    """Raised for gateway-workflow precondition failures (400/422 at the router)."""


def _now() -> datetime:
    return datetime.now(UTC)


def new_idempotency_key() -> str:
    return uuid4().hex


class PaymentRequestService:
    """Create, initiate, and confirm/fail/expire/cancel a ``PaymentRequest``."""

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, request_id: UUID) -> PaymentRequest | None:
        result = await db.execute(
            select(PaymentRequest)
            .where(PaymentRequest.id == request_id, PaymentRequest.clinic_id == clinic_id)
            .options(selectinload(PaymentRequest.refund_requests))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_for_payment(
        db: AsyncSession, clinic_id: UUID, payment_id: UUID
    ) -> PaymentRequest | None:
        """The gateway request behind a core Payment, if it was
        gateway-collected — the only place that association is known
        (``payments.Payment`` carries no provider field)."""
        result = await db.execute(
            select(PaymentRequest)
            .where(PaymentRequest.clinic_id == clinic_id, PaymentRequest.payment_id == payment_id)
            .options(selectinload(PaymentRequest.refund_requests))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_locked_by_provider_reference(
        db: AsyncSession, clinic_id: UUID, provider_key: str, provider_reference: str
    ) -> PaymentRequest | None:
        """Row-locked fetch for webhook handlers — the lock is what makes
        concurrent duplicate deliveries for the same event serialize
        instead of racing on the "already succeeded?" check."""
        result = await db.execute(
            select(PaymentRequest)
            .where(
                PaymentRequest.clinic_id == clinic_id,
                PaymentRequest.provider_key == provider_key,
                PaymentRequest.provider_reference == provider_reference,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_by_idempotency_key(
        db: AsyncSession, clinic_id: UUID, idempotency_key: str
    ) -> PaymentRequest | None:
        result = await db.execute(
            select(PaymentRequest).where(
                PaymentRequest.clinic_id == clinic_id,
                PaymentRequest.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_and_initiate(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        patient_id: UUID,
        provider_key: str,
        amount: Decimal,
        currency: str,
        method: str,
        allocations: list[dict],
        context: dict | None,
        created_by: UUID,
        idempotency_key: str | None = None,
    ) -> PaymentRequest:
        """Create a ``PaymentRequest`` and start the provider checkout.

        Reuses ``payments.workflow``'s own allocation-sum rule so a
        mismatch is rejected before ever calling the provider. A retry
        with the same ``idempotency_key`` returns the existing request
        instead of opening a second provider order.
        """
        idempotency_key = idempotency_key or new_idempotency_key()
        existing = await PaymentRequestService._get_by_idempotency_key(
            db, clinic_id, idempotency_key
        )
        if existing is not None:
            return existing

        adapter = gateway_registry.get(provider_key)
        if adapter is None:
            raise GatewayError(f"Unknown or inactive payment gateway provider {provider_key!r}")
        if method not in adapter.supported_methods:
            raise GatewayError(f"{provider_key} does not support method {method!r}")
        if not await adapter.supports(db, clinic_id):
            raise GatewayError(f"{provider_key} is not configured for this clinic")

        if not allocations:
            raise GatewayError("At least one allocation required")
        allocated_total = sum((Decimal(str(a["amount"])) for a in allocations), Decimal("0"))
        if allocated_total != amount:
            raise GatewayError(f"Allocations sum {allocated_total} does not match amount {amount}")

        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            raise GatewayError("Patient not found")

        request = PaymentRequest(
            clinic_id=clinic_id,
            patient_id=patient_id,
            provider_key=provider_key,
            requested_amount=amount,
            currency=currency,
            requested_method=method,
            state=PaymentRequestState.PENDING,
            allocation_input=allocations,
            context=context or {},
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
        db.add(request)
        await db.flush()  # need request.id before calling the adapter

        customer = GatewayCustomerInfo(
            name=f"{patient.first_name} {patient.last_name}".strip() or None,
            email=patient.email,
            phone=patient.phone,
        )
        try:
            checkout = await adapter.initiate_payment(db, request=request, customer=customer)
        except Exception as exc:  # noqa: BLE001 - provider transport/programmer errors
            validate_payment_request_transition(
                PaymentRequestState(request.state), PaymentRequestState.FAILED
            )
            request.state = PaymentRequestState.FAILED
            request.failed_at = _now()
            request.error_message = str(exc)[:500]
            # Commit now: the router turns the exception below into an
            # HTTPException, and FastAPI's get_db() dependency rolls
            # back the whole request session on ANY exception — without
            # this explicit commit, the failed row (and the reserved
            # idempotency key) would vanish along with it, leaving no
            # audit trail for the collect panel's "failed" state.
            await db.commit()
            raise GatewayError(f"Could not start payment with {provider_key}: {exc}") from exc

        request.provider_reference = checkout.provider_reference
        request.expires_at = checkout.expires_at
        request.checkout_payload_snapshot = {
            "redirect_url": checkout.redirect_url,
            "checkout_payload": checkout.checkout_payload,
            "qr_image_url": checkout.qr_image_url,
            "qr_payload": checkout.qr_payload,
        }
        request.raw_status_snapshot = {"provider_status": checkout.raw_provider_status}
        validate_payment_request_transition(
            PaymentRequestState(request.state), PaymentRequestState.AWAITING_CUSTOMER_ACTION
        )
        request.state = PaymentRequestState.AWAITING_CUSTOMER_ACTION
        await db.flush()
        return request

    @staticmethod
    async def confirm(
        db: AsyncSession,
        *,
        request: PaymentRequest,
        confirmation,  # adapters.GatewayConfirmation
        recorded_by: UUID | None = None,
    ) -> PaymentRequest:
        """Atomically create the core ``Payment`` and mark this request
        ``succeeded``. Idempotent: a request already ``succeeded`` is a
        no-op, so duplicate webhook delivery never creates a second
        Payment. Caller must hold a row lock on ``request`` (see
        :meth:`get_locked_by_provider_reference`) for the idempotency
        check to be race-free.

        Any terminal state (not just ``succeeded``) is treated as a
        no-op rather than a hard error: a "succeeded" confirmation
        arriving after we already marked the request ``failed``/
        ``expired``/``cancelled`` is a real provider-side race (a
        webhook can be delayed past our own timeout sweep), not a bug
        to crash on — and this module deliberately never auto-creates
        a Payment in that situation (the allocation target may no
        longer be valid). It is surfaced via ``raw_status_snapshot``
        for manual reconciliation rather than silently dropped.
        """
        if request.state in TERMINAL_REQUEST_STATES:
            if request.state != PaymentRequestState.SUCCEEDED:
                request.raw_status_snapshot = {
                    **(request.raw_status_snapshot or {}),
                    "late_confirmation_after_terminal_state": request.state,
                    "late_confirmation_provider_payment_reference": (
                        confirmation.provider_payment_reference
                    ),
                }
                await db.flush()
            return request  # duplicate delivery or late race — already resolved

        if (
            request.provider_payment_reference is not None
            and request.provider_payment_reference != confirmation.provider_payment_reference
        ):
            raise GatewayError(
                "Confirmation payment reference does not match the request's own reference"
            )
        if confirmation.amount != request.requested_amount:
            # Never silently record a different amount than the
            # allocations were computed against — that would break the
            # payments.workflow allocation-sum invariant.
            raise GatewayError(
                f"Confirmed amount {confirmation.amount} does not match "
                f"requested amount {request.requested_amount}"
            )

        validate_payment_request_transition(
            PaymentRequestState(request.state), PaymentRequestState.SUCCEEDED
        )

        try:
            payment = await record_payment(
                db,
                clinic_id=request.clinic_id,
                currency=request.currency,
                patient_id=request.patient_id,
                amount=request.requested_amount,
                method=confirmation.confirmed_method,
                payment_date=confirmation.captured_at.date(),
                recorded_by=recorded_by or request.created_by,
                allocations=request.allocation_input,
                reference=f"{request.provider_key}:{confirmation.provider_payment_reference}"[:100],
                notes=None,
                context=request.context,
            )
        except PaymentWorkflowError as exc:
            raise GatewayError(str(exc)) from exc

        request.payment_id = payment.id
        request.provider_payment_reference = confirmation.provider_payment_reference
        request.confirmed_at = confirmation.captured_at
        request.state = PaymentRequestState.SUCCEEDED
        await db.flush()
        return request

    @staticmethod
    async def fail(
        db: AsyncSession,
        *,
        request: PaymentRequest,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PaymentRequest:
        if request.state in TERMINAL_REQUEST_STATES:
            return request  # idempotent
        validate_payment_request_transition(
            PaymentRequestState(request.state), PaymentRequestState.FAILED
        )
        request.state = PaymentRequestState.FAILED
        request.failed_at = _now()
        request.error_code = error_code
        request.error_message = error_message
        await db.flush()
        return request

    @staticmethod
    async def expire(db: AsyncSession, *, request: PaymentRequest) -> PaymentRequest:
        if request.state in TERMINAL_REQUEST_STATES:
            return request
        validate_payment_request_transition(
            PaymentRequestState(request.state), PaymentRequestState.EXPIRED
        )
        request.state = PaymentRequestState.EXPIRED
        await db.flush()
        return request

    @staticmethod
    async def cancel(db: AsyncSession, *, request: PaymentRequest) -> PaymentRequest:
        if request.state in TERMINAL_REQUEST_STATES:
            return request
        validate_payment_request_transition(
            PaymentRequestState(request.state), PaymentRequestState.CANCELLED
        )
        request.state = PaymentRequestState.CANCELLED
        request.cancelled_at = _now()
        await db.flush()
        return request

    @staticmethod
    async def apply_webhook_event(
        db: AsyncSession, *, request: PaymentRequest, event: GatewayWebhookEvent
    ) -> PaymentRequest:
        """Dispatch a parsed webhook event onto the locked request. The
        caller (provider router) is responsible for the row lock and
        signature verification before this is ever called."""
        request.raw_status_snapshot = {
            **(request.raw_status_snapshot or {}),
            "last_event_type": event.event_type,
            "last_event_id": event.provider_event_id,
        }
        if event.event_type == "payment_succeeded" and event.confirmation is not None:
            return await PaymentRequestService.confirm(
                db, request=request, confirmation=event.confirmation
            )
        if event.event_type == "payment_authorized":
            if request.state in TERMINAL_REQUEST_STATES:
                return request
            validate_payment_request_transition(
                PaymentRequestState(request.state),
                PaymentRequestState.AUTHORISED_AWAITING_CAPTURE,
            )
            request.state = PaymentRequestState.AUTHORISED_AWAITING_CAPTURE
            await db.flush()
            return request
        if event.event_type == "payment_failed":
            return await PaymentRequestService.fail(
                db, request=request, error_code=event.error_code, error_message=event.error_message
            )
        if event.event_type == "payment_expired":
            return await PaymentRequestService.expire(db, request=request)
        if event.event_type == "payment_cancelled":
            return await PaymentRequestService.cancel(db, request=request)
        # "unrecognized" and refund_* events are handled by the caller
        # (refund_* dispatch onto GatewayRefundService — see router).
        await db.flush()
        return request


class GatewayRefundService:
    """Create and resolve a ``GatewayRefundRequest``.

    A core ``payments.Refund`` is created only from :meth:`complete` —
    never from :meth:`request_refund`, even when the provider is asked
    to refund immediately (see the module CLAUDE.md gotcha on
    synchronous-looking providers).
    """

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, refund_request_id: UUID
    ) -> GatewayRefundRequest | None:
        result = await db.execute(
            select(GatewayRefundRequest).where(
                GatewayRefundRequest.id == refund_request_id,
                GatewayRefundRequest.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_payment(
        db: AsyncSession, clinic_id: UUID, payment_id: UUID
    ) -> list[GatewayRefundRequest]:
        result = await db.execute(
            select(GatewayRefundRequest)
            .where(
                GatewayRefundRequest.clinic_id == clinic_id,
                GatewayRefundRequest.payment_id == payment_id,
            )
            .order_by(GatewayRefundRequest.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_locked_by_provider_reference(
        db: AsyncSession, clinic_id: UUID, provider_key: str, provider_refund_reference: str
    ) -> GatewayRefundRequest | None:
        result = await db.execute(
            select(GatewayRefundRequest)
            .where(
                GatewayRefundRequest.clinic_id == clinic_id,
                GatewayRefundRequest.provider_key == provider_key,
                GatewayRefundRequest.provider_refund_reference == provider_refund_reference,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_by_idempotency_key(
        db: AsyncSession, clinic_id: UUID, idempotency_key: str
    ) -> GatewayRefundRequest | None:
        result = await db.execute(
            select(GatewayRefundRequest).where(
                GatewayRefundRequest.clinic_id == clinic_id,
                GatewayRefundRequest.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _refundable_amount(db: AsyncSession, clinic_id: UUID, payment: Payment) -> Decimal:
        """``payment.amount`` minus already-*completed* core refunds.

        Gateway refunds still ``requested``/``processing`` are
        deliberately not reserved against this — see the module
        CLAUDE.md gotcha on the accepted race with concurrent refund
        attempts; ``payments.workflow.refund_payment``'s own row-locked
        cap check at :meth:`complete` time is the final backstop.
        """
        result = await db.execute(
            select(func.coalesce(func.sum(Refund.amount), Decimal("0"))).where(
                Refund.payment_id == payment.id, Refund.clinic_id == clinic_id
            )
        )
        already_refunded: Decimal = result.scalar_one()
        return payment.amount - already_refunded

    @staticmethod
    async def request_refund(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        payment: Payment,
        payment_request: PaymentRequest,
        amount: Decimal,
        reason_code: str,
        reason_note: str | None,
        requested_by: UUID,
        idempotency_key: str | None = None,
    ) -> GatewayRefundRequest:
        if amount <= 0:
            raise GatewayError("Refund amount must be > 0")

        idempotency_key = idempotency_key or new_idempotency_key()
        existing = await GatewayRefundService._get_by_idempotency_key(
            db, clinic_id, idempotency_key
        )
        if existing is not None:
            return existing

        refundable = await GatewayRefundService._refundable_amount(db, clinic_id, payment)
        if amount > refundable:
            raise GatewayError(
                f"Refund {amount} exceeds remaining refundable amount {refundable} "
                f"for payment {payment.id}"
            )

        adapter = gateway_registry.get(payment_request.provider_key)
        if adapter is None:
            raise GatewayError(
                f"Unknown or inactive payment gateway provider {payment_request.provider_key!r}"
            )

        if not payment_request.provider_payment_reference:
            raise GatewayError("Payment request has no confirmed provider payment reference")

        refund_request = GatewayRefundRequest(
            clinic_id=clinic_id,
            payment_id=payment.id,
            payment_request_id=payment_request.id,
            provider_key=payment_request.provider_key,
            provider_payment_reference=payment_request.provider_payment_reference,
            requested_amount=amount,
            reason_code=reason_code,
            reason_note=reason_note,
            state=GatewayRefundState.REQUESTED,
            idempotency_key=idempotency_key,
            requested_by=requested_by,
        )
        db.add(refund_request)
        await db.flush()

        try:
            result = await adapter.initiate_refund(db, refund_request=refund_request)
        except Exception as exc:  # noqa: BLE001 - provider transport/programmer errors
            refund_request.state = GatewayRefundState.FAILED
            refund_request.failed_at = _now()
            refund_request.error_message = str(exc)[:500]
            # Commit before raising — see the matching comment in
            # PaymentRequestService.create_and_initiate.
            await db.commit()
            raise GatewayError(
                f"Could not start refund with {payment_request.provider_key}: {exc}"
            ) from exc

        refund_request.provider_refund_reference = result.provider_refund_reference

        if result.state == GatewayRefundState.COMPLETED:
            # Some providers resolve synchronously — but the core Refund
            # is still only created here, inside complete(), never
            # inline, so there is exactly one code path that writes it.
            await GatewayRefundService.complete(db, refund_request=refund_request)
        elif result.state == GatewayRefundState.FAILED:
            refund_request.state = GatewayRefundState.FAILED
            refund_request.failed_at = _now()
            refund_request.error_code = result.error_code
            refund_request.error_message = result.error_message
            await db.flush()
        else:
            validate_refund_transition(
                GatewayRefundState(refund_request.state), GatewayRefundState.PROCESSING
            )
            refund_request.state = GatewayRefundState.PROCESSING
            await db.flush()

        return refund_request

    @staticmethod
    async def mark_processing(
        db: AsyncSession, *, refund_request: GatewayRefundRequest
    ) -> GatewayRefundRequest:
        if refund_request.state in TERMINAL_REFUND_STATES:
            return refund_request
        if refund_request.state == GatewayRefundState.PROCESSING:
            return refund_request
        validate_refund_transition(
            GatewayRefundState(refund_request.state), GatewayRefundState.PROCESSING
        )
        refund_request.state = GatewayRefundState.PROCESSING
        await db.flush()
        return refund_request

    @staticmethod
    async def complete(
        db: AsyncSession,
        *,
        refund_request: GatewayRefundRequest,
        completed_at: datetime | None = None,
    ) -> GatewayRefundRequest:
        """Atomically create the core ``Refund`` and mark this request
        ``completed``. Idempotent: a request already ``completed`` is a
        no-op. Caller must hold a row lock (see
        :meth:`get_locked_by_provider_reference`) for the idempotency
        check to be race-free when called from a webhook.
        """
        if refund_request.state == GatewayRefundState.COMPLETED:
            return refund_request

        validate_refund_transition(
            GatewayRefundState(refund_request.state), GatewayRefundState.COMPLETED
        )

        payment = await PaymentService.get(db, refund_request.clinic_id, refund_request.payment_id)
        if payment is None:  # pragma: no cover - defensive, FK guarantees existence
            raise GatewayError("Original payment not found")

        try:
            refund = await refund_payment(
                db,
                clinic_id=refund_request.clinic_id,
                payment=payment,
                amount=refund_request.requested_amount,
                method=payment.method,
                reason_code=refund_request.reason_code,
                reason_note=refund_request.reason_note,
                refunded_by=refund_request.requested_by,
            )
        except PaymentWorkflowError as exc:
            # The core cap check is the final backstop (see
            # _refundable_amount's docstring) — surface it as a failed
            # gateway refund rather than raising past a webhook handler.
            refund_request.state = GatewayRefundState.FAILED
            refund_request.failed_at = _now()
            refund_request.error_message = str(exc)[:500]
            # Commit before raising — see the matching comment in
            # PaymentRequestService.create_and_initiate. Safe even when
            # called from the webhook handler (which swallows
            # GatewayError and would have committed anyway).
            await db.commit()
            raise GatewayError(str(exc)) from exc

        refund_request.refund_id = refund.id
        refund_request.state = GatewayRefundState.COMPLETED
        refund_request.completed_at = completed_at or _now()
        await db.flush()
        return refund_request

    @staticmethod
    async def fail(
        db: AsyncSession,
        *,
        refund_request: GatewayRefundRequest,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> GatewayRefundRequest:
        if refund_request.state in TERMINAL_REFUND_STATES:
            return refund_request
        validate_refund_transition(
            GatewayRefundState(refund_request.state), GatewayRefundState.FAILED
        )
        refund_request.state = GatewayRefundState.FAILED
        refund_request.failed_at = _now()
        refund_request.error_code = error_code
        refund_request.error_message = error_message
        await db.flush()
        return refund_request
