"""GatewayRefundRequest creation and resolution.

Uses ``FakeAdapter`` (conftest) — no network, no real provider.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.auth.models import User
from app.core.auth.service import create_access_token, hash_password
from app.modules.payment_gateways.adapters import GatewayRefundInitResult
from app.modules.payment_gateways.constants import GatewayRefundState
from app.modules.payment_gateways.service import (
    GatewayError,
    GatewayRefundService,
    PaymentRequestService,
)
from app.modules.payments.models import Refund
from app.modules.payments.service import PaymentService

from .conftest import make_confirmation


async def _confirmed_payment(
    db_session,
    fake_adapter,
    gateway_clinic,
    gateway_patient,
    gateway_user_id,
    amount=Decimal("500.00"),
):
    request = await PaymentRequestService.create_and_initiate(
        db_session,
        clinic_id=gateway_clinic.id,
        patient_id=gateway_patient.id,
        provider_key="fake",
        amount=amount,
        currency="INR",
        method="upi",
        allocations=[{"target_type": "on_account", "amount": str(amount)}],
        context=None,
        created_by=gateway_user_id,
    )
    confirmed = await PaymentRequestService.confirm(
        db_session, request=request, confirmation=make_confirmation(amount=amount)
    )
    payment = await PaymentService.get(db_session, gateway_clinic.id, confirmed.payment_id)
    return confirmed, payment


async def test_refund_processing_creates_no_core_refund_yet(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    refund_request = await GatewayRefundService.request_refund(
        db_session,
        clinic_id=gateway_clinic.id,
        payment=payment,
        payment_request=request,
        amount=Decimal("200.00"),
        reason_code="duplicate",
        reason_note=None,
        requested_by=gateway_user_id,
    )
    assert refund_request.state == GatewayRefundState.PROCESSING
    assert refund_request.refund_id is None

    count = (
        await db_session.execute(
            select(func.count()).select_from(Refund).where(Refund.payment_id == payment.id)
        )
    ).scalar()
    assert count == 0


async def test_refund_completion_creates_exactly_one_core_refund(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    refund_request = await GatewayRefundService.request_refund(
        db_session,
        clinic_id=gateway_clinic.id,
        payment=payment,
        payment_request=request,
        amount=Decimal("200.00"),
        reason_code="duplicate",
        reason_note=None,
        requested_by=gateway_user_id,
    )
    completed = await GatewayRefundService.complete(db_session, refund_request=refund_request)
    assert completed.state == GatewayRefundState.COMPLETED
    assert completed.refund_id is not None

    count = (
        await db_session.execute(
            select(func.count()).select_from(Refund).where(Refund.payment_id == payment.id)
        )
    ).scalar()
    assert count == 1


async def test_duplicate_completion_event_is_idempotent(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    refund_request = await GatewayRefundService.request_refund(
        db_session,
        clinic_id=gateway_clinic.id,
        payment=payment,
        payment_request=request,
        amount=Decimal("200.00"),
        reason_code="duplicate",
        reason_note=None,
        requested_by=gateway_user_id,
    )
    first = await GatewayRefundService.complete(db_session, refund_request=refund_request)
    second = await GatewayRefundService.complete(db_session, refund_request=refund_request)
    assert first.refund_id == second.refund_id

    count = (
        await db_session.execute(
            select(func.count()).select_from(Refund).where(Refund.payment_id == payment.id)
        )
    ).scalar()
    assert count == 1


async def test_synchronous_provider_completion_still_only_writes_refund_once(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    """Some providers resolve a refund synchronously in the API response
    — the fast path in request_refund() must still route through
    complete(), never construct a core Refund inline."""
    request, payment = await _confirmed_payment(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    fake_adapter.next_refund_result = GatewayRefundInitResult(
        provider_refund_reference="fake_refund_sync", state=str(GatewayRefundState.COMPLETED)
    )
    refund_request = await GatewayRefundService.request_refund(
        db_session,
        clinic_id=gateway_clinic.id,
        payment=payment,
        payment_request=request,
        amount=Decimal("100.00"),
        reason_code="overpaid",
        reason_note=None,
        requested_by=gateway_user_id,
    )
    assert refund_request.state == GatewayRefundState.COMPLETED
    assert refund_request.refund_id is not None
    count = (
        await db_session.execute(
            select(func.count()).select_from(Refund).where(Refund.payment_id == payment.id)
        )
    ).scalar()
    assert count == 1


async def test_refund_cannot_exceed_remaining_refundable_amount(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session,
        fake_adapter,
        gateway_clinic,
        gateway_patient,
        gateway_user_id,
        amount=Decimal("300.00"),
    )
    with pytest.raises(GatewayError, match="exceeds remaining refundable amount"):
        await GatewayRefundService.request_refund(
            db_session,
            clinic_id=gateway_clinic.id,
            payment=payment,
            payment_request=request,
            amount=Decimal("300.01"),
            reason_code="duplicate",
            reason_note=None,
            requested_by=gateway_user_id,
        )
    assert len(fake_adapter.refund_calls) == 0  # never even reaches the provider


async def test_refund_cap_accounts_for_already_completed_refunds(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session,
        fake_adapter,
        gateway_clinic,
        gateway_patient,
        gateway_user_id,
        amount=Decimal("300.00"),
    )
    first = await GatewayRefundService.request_refund(
        db_session,
        clinic_id=gateway_clinic.id,
        payment=payment,
        payment_request=request,
        amount=Decimal("200.00"),
        reason_code="duplicate",
        reason_note=None,
        requested_by=gateway_user_id,
    )
    await GatewayRefundService.complete(db_session, refund_request=first)

    with pytest.raises(GatewayError, match="exceeds remaining refundable amount"):
        await GatewayRefundService.request_refund(
            db_session,
            clinic_id=gateway_clinic.id,
            payment=payment,
            payment_request=request,
            amount=Decimal("100.01"),
            reason_code="duplicate",
            reason_note=None,
            requested_by=gateway_user_id,
        )


async def test_adapter_failure_marks_refund_failed_and_persists_no_core_refund(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    fake_adapter.refund_should_raise = RuntimeError("provider outage")
    with pytest.raises(GatewayError, match="Could not start refund"):
        await GatewayRefundService.request_refund(
            db_session,
            clinic_id=gateway_clinic.id,
            payment=payment,
            payment_request=request,
            amount=Decimal("50.00"),
            reason_code="duplicate",
            reason_note=None,
            requested_by=gateway_user_id,
        )

    from app.modules.payment_gateways.models import GatewayRefundRequest

    row = (
        await db_session.execute(
            select(GatewayRefundRequest).where(GatewayRefundRequest.payment_id == payment.id)
        )
    ).scalar_one()
    assert row.state == GatewayRefundState.FAILED
    assert row.refund_id is None


# --- Authorization -------------------------------------------------------


async def test_refund_endpoint_requires_refund_permission(
    client, db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request, payment = await _confirmed_payment(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )

    from app.core.auth.models import ClinicMembership

    receptionist = User(
        id=uuid4(),
        email="reception@test.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Recep",
        last_name="Tionist",
    )
    db_session.add(receptionist)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(), user_id=receptionist.id, clinic_id=gateway_clinic.id, role="receptionist"
        )
    )
    await db_session.commit()
    token = create_access_token(receptionist.id, token_version=receptionist.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/payment_gateways/refunds",
        json={
            "payment_id": str(payment.id),
            "amount": "50.00",
            "reason_code": "duplicate",
        },
        headers=headers,
    )
    assert resp.status_code == 403
