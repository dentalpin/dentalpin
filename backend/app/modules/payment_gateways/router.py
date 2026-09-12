"""payment_gateways HTTP surface — mounted at ``/api/v1/payment_gateways/``.

Deliberately reuses the ``payments`` module's own permission strings
(``payments.record.{read,write,refund}``) rather than declaring new
ones: initiating a gateway collection or refund *is* recording a
payment/refund in every way that matters to an authorizer, and a
module-own permission would only drift out of sync with payments' own
role grants (same cross-module reuse precedent as india_gst reusing
``billing.write`` for draft-invoice GST fields).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.payments.service import PaymentService

from .schemas import (
    GatewayInfoResponse,
    GatewayRefundRequestCreate,
    GatewayRefundRequestResponse,
    PaymentRequestCreate,
    PaymentRequestResponse,
)
from .service import GatewayError, GatewayRefundService, PaymentRequestService

router = APIRouter()


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Payment requests --------------------------------------------------


@router.post("/requests", response_model=ApiResponse[PaymentRequestResponse], status_code=201)
async def create_request(
    payload: PaymentRequestCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentRequestResponse]:
    try:
        request = await PaymentRequestService.create_and_initiate(
            db,
            clinic_id=ctx.clinic_id,
            patient_id=payload.patient_id,
            provider_key=payload.provider_key,
            amount=payload.amount,
            currency=ctx.clinic.currency,
            method=payload.method,
            # mode="json" so Decimal amounts serialize as strings — this
            # dict is stored verbatim in the JSONB allocation_input
            # column, which cannot encode a raw Decimal.
            allocations=[a.model_dump(mode="json") for a in payload.allocations],
            context=payload.context,
            created_by=ctx.user_id,
            idempotency_key=payload.idempotency_key,
        )
    except GatewayError as exc:
        raise _bad_request(exc)
    return ApiResponse(data=PaymentRequestResponse.from_model(request))


@router.get("/requests/{request_id}", response_model=ApiResponse[PaymentRequestResponse])
async def get_request(
    request_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentRequestResponse]:
    request = await PaymentRequestService.get(db, ctx.clinic_id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return ApiResponse(data=PaymentRequestResponse.from_model(request))


@router.post("/requests/{request_id}/refresh", response_model=ApiResponse[PaymentRequestResponse])
async def refresh_request(
    request_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentRequestResponse]:
    """On-demand status pull — for a stuck ``awaiting_customer_action``
    request when the UI wants a manual refresh rather than wait for
    the next webhook retry. The webhook remains the primary,
    authoritative confirmation path; this never trusts a client-side
    "payment succeeded" claim."""
    from .adapters import gateway_registry

    request = await PaymentRequestService.get(db, ctx.clinic_id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Payment request not found")

    adapter = gateway_registry.get(request.provider_key)
    if adapter is None:
        raise HTTPException(status_code=409, detail=f"Provider {request.provider_key} unavailable")

    status_result = await adapter.verify_payment_status(db, request=request)
    try:
        if status_result.state == "succeeded" and status_result.confirmation is not None:
            request = await PaymentRequestService.confirm(
                db, request=request, confirmation=status_result.confirmation
            )
        elif status_result.state == "failed":
            request = await PaymentRequestService.fail(
                db,
                request=request,
                error_code=status_result.error_code,
                error_message=status_result.error_message,
            )
        elif status_result.state == "expired":
            request = await PaymentRequestService.expire(db, request=request)
    except GatewayError as exc:
        raise _bad_request(exc)
    return ApiResponse(data=PaymentRequestResponse.from_model(request))


@router.post("/requests/{request_id}/cancel", response_model=ApiResponse[PaymentRequestResponse])
async def cancel_request(
    request_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentRequestResponse]:
    request = await PaymentRequestService.get(db, ctx.clinic_id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Payment request not found")
    try:
        request = await PaymentRequestService.cancel(db, request=request)
    except GatewayError as exc:
        raise _bad_request(exc)
    return ApiResponse(data=PaymentRequestResponse.from_model(request))


# --- Transaction detail (gateway info for a core Payment) ---------------


@router.get("/payments/{payment_id}/gateway-info", response_model=ApiResponse[GatewayInfoResponse])
async def gateway_info_for_payment(
    payment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GatewayInfoResponse]:
    request = await PaymentRequestService.get_for_payment(db, ctx.clinic_id, payment_id)
    if request is None:
        return ApiResponse(data=GatewayInfoResponse(request=None, refund_requests=[]))
    return ApiResponse(
        data=GatewayInfoResponse(
            request=PaymentRequestResponse.from_model(request),
            refund_requests=[
                GatewayRefundRequestResponse.model_validate(r) for r in request.refund_requests
            ],
        )
    )


# --- Gateway refunds -----------------------------------------------------


@router.post("/refunds", response_model=ApiResponse[GatewayRefundRequestResponse], status_code=201)
async def create_refund(
    payload: GatewayRefundRequestCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.refund"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GatewayRefundRequestResponse]:
    payment = await PaymentService.get(db, ctx.clinic_id, payload.payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment_request = await PaymentRequestService.get_for_payment(
        db, ctx.clinic_id, payload.payment_id
    )
    if payment_request is None:
        raise HTTPException(
            status_code=400, detail="This payment was not collected through a payment gateway"
        )

    try:
        refund_request = await GatewayRefundService.request_refund(
            db,
            clinic_id=ctx.clinic_id,
            payment=payment,
            payment_request=payment_request,
            amount=payload.amount,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            requested_by=ctx.user_id,
            idempotency_key=payload.idempotency_key,
        )
    except GatewayError as exc:
        raise _bad_request(exc)
    return ApiResponse(data=GatewayRefundRequestResponse.model_validate(refund_request))


@router.get(
    "/refunds/{refund_request_id}", response_model=ApiResponse[GatewayRefundRequestResponse]
)
async def get_refund(
    refund_request_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GatewayRefundRequestResponse]:
    refund_request = await GatewayRefundService.get(db, ctx.clinic_id, refund_request_id)
    if refund_request is None:
        raise HTTPException(status_code=404, detail="Gateway refund request not found")
    return ApiResponse(data=GatewayRefundRequestResponse.model_validate(refund_request))


@router.get(
    "/payments/{payment_id}/refunds", response_model=ApiResponse[list[GatewayRefundRequestResponse]]
)
async def list_refunds_for_payment(
    payment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[GatewayRefundRequestResponse]]:
    rows = await GatewayRefundService.list_for_payment(db, ctx.clinic_id, payment_id)
    return ApiResponse(data=[GatewayRefundRequestResponse.model_validate(r) for r in rows])
