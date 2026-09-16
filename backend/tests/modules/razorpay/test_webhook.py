"""Razorpay webhook: signature verification, idempotent confirmation,
failed/expired/cancelled paths. No network — the webhook endpoint
itself never calls out to Razorpay, only verifies an inbound HMAC
signature and dispatches into payment_gateways.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.payment_gateways.constants import GatewayRefundState, PaymentRequestState
from app.modules.payment_gateways.models import GatewayRefundRequest, PaymentRequest
from app.modules.payments.models import Payment, Refund
from app.modules.razorpay.models import RazorpaySettings
from app.modules.razorpay.service import RazorpaySettingsService

from .conftest import sign


async def _make_request(
    db_session: AsyncSession,
    *,
    clinic: Clinic,
    patient: Patient,
    user_id,
    provider_reference: str,
    amount: Decimal = Decimal("500.00"),
) -> PaymentRequest:
    request = PaymentRequest(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        provider_key="razorpay",
        requested_amount=amount,
        currency="INR",
        requested_method="upi",
        state=PaymentRequestState.AWAITING_CUSTOMER_ACTION,
        allocation_input=[{"target_type": "on_account", "target_id": None, "amount": str(amount)}],
        context={},
        idempotency_key=str(uuid4()),
        provider_reference=provider_reference,
        created_by=user_id,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


def _captured_payload(
    order_id: str, payment_id: str, amount_paise: int = 50000, method: str = "upi"
) -> dict:
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "amount": amount_paise,
                    "currency": "INR",
                    "method": method,
                    "captured": True,
                    "created_at": 1700000000,
                }
            }
        },
    }


async def test_webhook_rejects_invalid_signature(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    request = await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_BADSIG",
    )
    body, _ = sign(_captured_payload("order_BADSIG", "pay_BADSIG"))

    resp = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=body,
        headers={
            "X-Razorpay-Signature": "not-the-real-signature",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401

    await db_session.refresh(request)
    assert request.state == PaymentRequestState.AWAITING_CUSTOMER_ACTION  # untouched

    # record_webhook_error only flush()es; without an explicit commit
    # before the 401 is raised, get_db() rolling back the session would
    # wipe this out along with everything else, leaving no trail for
    # diagnosing a misconfigured/rotated webhook secret.
    await db_session.refresh(razorpay_settings)
    assert razorpay_settings.last_webhook_error is not None
    assert razorpay_settings.last_webhook_error_at is not None


async def test_webhook_processing_error_persists_webhook_health_before_500(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
):
    """A genuine processing exception (not a GatewayError, e.g. a
    malformed provider payload) still answers 500 so Razorpay retries —
    but the webhook-health bookkeeping recorded on the way there must
    survive that response, same reasoning as the 401 path above."""
    body, sig = sign(_captured_payload("order_BOOM", "pay_BOOM", amount_paise="not-a-number"))

    resp = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 500

    await db_session.refresh(razorpay_settings)
    assert razorpay_settings.last_webhook_error is not None
    assert razorpay_settings.last_webhook_error_at is not None


async def test_webhook_failure_after_confirm_rolls_back_payment_and_persists_error(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
    monkeypatch,
):
    """A failure that hits *after* ``confirm()`` has already flushed a
    Payment + allocations (here simulated via a broken
    ``record_webhook_processed`` call) must roll back that partial
    confirmation before recording the webhook error — a plain commit at
    that point would otherwise persist a half-applied confirmation
    alongside the error record, and a Razorpay retry would land on
    partially-committed state instead of a clean one (review follow-up,
    PR #470)."""
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    request = await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_ROLLBACK1",
    )
    # `db.rollback()` inside the handler under test expires every object
    # in this (shared, per-test) session, including `test_clinic` itself
    # — capture the plain id up front rather than touching the ORM
    # instance again after the first request.
    clinic_id = test_clinic.id
    body, sig = sign(_captured_payload("order_ROLLBACK1", "pay_ROLLBACK1"))
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    async def _boom(db, settings):
        raise RuntimeError("simulated failure after confirmation flush")

    monkeypatch.setattr(RazorpaySettingsService, "record_webhook_processed", _boom)

    resp = await client.post(f"/api/v1/razorpay/webhook/{clinic_id}", content=body, headers=headers)
    assert resp.status_code == 500

    # The confirmation that had already been flushed (PaymentRequest ->
    # succeeded, Payment + allocations) must not have survived.
    await db_session.refresh(request)
    assert request.state == PaymentRequestState.AWAITING_CUSTOMER_ACTION
    assert request.payment_id is None
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.reference == "razorpay:pay_ROLLBACK1")
        )
    ).scalar()
    assert count == 0

    # But the webhook error was recorded against a fresh, clean row.
    await db_session.refresh(razorpay_settings)
    assert razorpay_settings.last_webhook_error is not None
    assert "simulated failure" in razorpay_settings.last_webhook_error
    assert razorpay_settings.last_webhook_error_at is not None

    # A retry from this clean state processes normally.
    monkeypatch.undo()
    resp2 = await client.post(
        f"/api/v1/razorpay/webhook/{clinic_id}", content=body, headers=headers
    )
    assert resp2.status_code == 200

    await db_session.refresh(request)
    assert request.state == PaymentRequestState.SUCCEEDED
    assert request.payment_id is not None
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.reference == "razorpay:pay_ROLLBACK1")
        )
    ).scalar()
    assert count == 1


async def test_webhook_unknown_clinic_accepts_and_ignores(client: AsyncClient):
    body, sig = sign(_captured_payload("order_X", "pay_X"))
    resp = await client.post(
        f"/api/v1/razorpay/webhook/{uuid4()}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200  # accept-and-ignore, never leaks existence via error differences


async def test_verified_webhook_creates_exactly_one_payment_with_upi_method(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    request = await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_OK1",
    )
    body, sig = sign(_captured_payload("order_OK1", "pay_OK1", amount_paise=50000))

    resp = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    await db_session.refresh(request)
    assert request.state == PaymentRequestState.SUCCEEDED
    assert request.provider_payment_reference == "pay_OK1"
    assert request.payment_id is not None

    payment = (
        await db_session.execute(select(Payment).where(Payment.id == request.payment_id))
    ).scalar_one()
    assert payment.method == "upi"
    assert payment.amount == Decimal("500.00")
    assert payment.patient_id == test_patient.id
    assert "razorpay:pay_OK1" in (payment.reference or "")

    count = (
        await db_session.execute(
            select(func.count()).select_from(Payment).where(Payment.patient_id == test_patient.id)
        )
    ).scalar()
    assert count == 1


async def test_duplicate_webhook_delivery_never_creates_a_second_payment(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_DUP1",
    )
    body, sig = sign(_captured_payload("order_DUP1", "pay_DUP1"))
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    r1 = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}", content=body, headers=headers
    )
    r2 = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}", content=body, headers=headers
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.reference == "razorpay:pay_DUP1")
        )
    ).scalar()
    assert count == 1


async def test_failed_event_transitions_request_without_creating_a_payment(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    request = await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_FAIL1",
    )
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_FAIL1",
                    "order_id": "order_FAIL1",
                    "error_code": "GATEWAY_ERROR",
                    "error_description": "insufficient funds",
                }
            }
        },
    }
    body, sig = sign(payload)
    resp = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    await db_session.refresh(request)
    assert request.state == PaymentRequestState.FAILED
    assert request.payment_id is None
    assert "insufficient funds" in (request.error_message or "")


async def test_webhook_updates_settings_health(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_HEALTH1",
    )
    body, sig = sign(_captured_payload("order_HEALTH1", "pay_HEALTH1"))
    await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )

    await db_session.refresh(razorpay_settings)
    assert razorpay_settings.last_webhook_received_at is not None
    assert razorpay_settings.last_webhook_processed_at is not None
    assert razorpay_settings.last_webhook_event_type == "payment.captured"


async def test_refund_processed_webhook_completes_refund_exactly_once(
    client: AsyncClient,
    db_session: AsyncSession,
    razorpay_settings: RazorpaySettings,
    test_clinic,
    test_patient,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    request = await _make_request(
        db_session,
        clinic=test_clinic,
        patient=test_patient,
        user_id=user_id,
        provider_reference="order_RF1",
    )
    body, sig = sign(_captured_payload("order_RF1", "pay_RF1"))
    await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    await db_session.refresh(request)

    refund_request = GatewayRefundRequest(
        id=uuid4(),
        clinic_id=test_clinic.id,
        payment_id=request.payment_id,
        payment_request_id=request.id,
        provider_key="razorpay",
        provider_payment_reference="pay_RF1",
        requested_amount=Decimal("100.00"),
        reason_code="duplicate",
        state=GatewayRefundState.PROCESSING,
        idempotency_key=str(uuid4()),
        provider_refund_reference="rfnd_RF1",
        requested_by=user_id,
    )
    db_session.add(refund_request)
    await db_session.commit()

    refund_payload = {
        "event": "refund.processed",
        "payload": {"refund": {"entity": {"id": "rfnd_RF1"}}},
    }
    rbody, rsig = sign(refund_payload)
    r1 = await client.post(
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=rbody,
        headers={"X-Razorpay-Signature": rsig, "Content-Type": "application/json"},
    )
    r2 = await client.post(  # duplicate delivery
        f"/api/v1/razorpay/webhook/{test_clinic.id}",
        content=rbody,
        headers={"X-Razorpay-Signature": rsig, "Content-Type": "application/json"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    await db_session.refresh(refund_request)
    assert refund_request.state == GatewayRefundState.COMPLETED
    count = (
        await db_session.execute(
            select(func.count()).select_from(Refund).where(Refund.payment_id == request.payment_id)
        )
    ).scalar()
    assert count == 1
