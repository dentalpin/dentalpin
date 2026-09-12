"""PaymentRequest creation, confirmation, and idempotency.

Uses ``FakeAdapter`` (conftest) — no network, no real provider.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.modules.payment_gateways.constants import (
    PaymentRequestState,
    PaymentRequestTransitionError,
)
from app.modules.payment_gateways.service import GatewayError, PaymentRequestService
from app.modules.payments.models import Payment

from .conftest import make_confirmation


async def _create(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id, **overrides
):
    kwargs = dict(
        clinic_id=gateway_clinic.id,
        patient_id=gateway_patient.id,
        provider_key="fake",
        amount=Decimal("500.00"),
        currency="INR",
        method="upi",
        allocations=[{"target_type": "on_account", "amount": "500.00"}],
        context=None,
        created_by=gateway_user_id,
    )
    kwargs.update(overrides)
    return await PaymentRequestService.create_and_initiate(db_session, **kwargs)


async def test_create_and_initiate_happy_path(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    assert request.state == PaymentRequestState.AWAITING_CUSTOMER_ACTION
    assert request.provider_reference == "fake_order_1"
    assert request.checkout_payload_snapshot is not None
    assert len(fake_adapter.initiate_calls) == 1


async def test_create_rejects_allocation_sum_mismatch(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    with pytest.raises(GatewayError, match="does not match"):
        await _create(
            db_session,
            fake_adapter,
            gateway_clinic,
            gateway_patient,
            gateway_user_id,
            allocations=[{"target_type": "on_account", "amount": "1.00"}],
        )
    assert len(fake_adapter.initiate_calls) == 0  # never even reaches the provider


async def test_create_rejects_unsupported_method(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    with pytest.raises(GatewayError, match="does not support"):
        await _create(
            db_session,
            fake_adapter,
            gateway_clinic,
            gateway_patient,
            gateway_user_id,
            method="netbanking",
        )


async def test_create_rejects_unknown_provider(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    with pytest.raises(GatewayError, match="Unknown or inactive"):
        await _create(
            db_session,
            fake_adapter,
            gateway_clinic,
            gateway_patient,
            gateway_user_id,
            provider_key="ghost",
        )


async def test_create_rejects_when_adapter_not_configured_for_clinic(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    fake_adapter.unsupported_clinics.add(gateway_clinic.id)
    with pytest.raises(GatewayError, match="not configured"):
        await _create(db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id)


async def test_create_is_idempotent_on_retry_key(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    r1 = await _create(
        db_session,
        fake_adapter,
        gateway_clinic,
        gateway_patient,
        gateway_user_id,
        idempotency_key="retry-1",
    )
    r2 = await _create(
        db_session,
        fake_adapter,
        gateway_clinic,
        gateway_patient,
        gateway_user_id,
        idempotency_key="retry-1",
    )
    assert r1.id == r2.id
    assert len(fake_adapter.initiate_calls) == 1  # provider was only ever asked once


async def test_adapter_failure_marks_request_failed_and_persists(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    fake_adapter.initiate_should_raise = RuntimeError("provider outage")
    with pytest.raises(GatewayError, match="Could not start payment"):
        await _create(db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id)

    # The service commits the failed row explicitly before raising —
    # confirm it actually survives (would vanish on a bare db.flush()
    # since the router-level exception rolls the request session back).
    from app.modules.payment_gateways.models import PaymentRequest

    row = (
        await db_session.execute(
            select(PaymentRequest).where(PaymentRequest.clinic_id == gateway_clinic.id)
        )
    ).scalar_one()
    assert row.state == PaymentRequestState.FAILED
    assert "provider outage" in row.error_message


async def test_confirm_creates_exactly_one_payment(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    confirmation = make_confirmation(amount=Decimal("500.00"))

    confirmed = await PaymentRequestService.confirm(
        db_session, request=request, confirmation=confirmation
    )

    assert confirmed.state == PaymentRequestState.SUCCEEDED
    assert confirmed.payment_id is not None
    assert confirmed.provider_payment_reference == "fake_pay_1"

    count = (
        await db_session.execute(
            select(func.count()).select_from(Payment).where(Payment.id == confirmed.payment_id)
        )
    ).scalar()
    assert count == 1

    payment = (
        await db_session.execute(select(Payment).where(Payment.id == confirmed.payment_id))
    ).scalar_one()
    assert payment.method == "upi"
    assert payment.amount == Decimal("500.00")
    assert payment.patient_id == gateway_patient.id


async def test_confirm_is_idempotent_duplicate_webhook_never_double_pays(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    confirmation = make_confirmation(amount=Decimal("500.00"))

    first = await PaymentRequestService.confirm(
        db_session, request=request, confirmation=confirmation
    )
    second = await PaymentRequestService.confirm(
        db_session, request=request, confirmation=confirmation
    )

    assert first.payment_id == second.payment_id
    total = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.patient_id == gateway_patient.id)
        )
    ).scalar()
    assert total == 1


async def test_confirm_rejects_amount_mismatch_and_creates_no_payment(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    wrong_amount_confirmation = make_confirmation(amount=Decimal("1.00"))

    with pytest.raises(GatewayError, match="does not match"):
        await PaymentRequestService.confirm(
            db_session, request=request, confirmation=wrong_amount_confirmation
        )

    total = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.patient_id == gateway_patient.id)
        )
    ).scalar()
    assert total == 0


@pytest.mark.parametrize("terminal_method", ["fail", "expire", "cancel"])
async def test_terminal_paths_never_create_a_payment(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id, terminal_method
):
    request = await _create(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )

    if terminal_method == "fail":
        result = await PaymentRequestService.fail(
            db_session, request=request, error_message="declined"
        )
        assert result.state == PaymentRequestState.FAILED
    elif terminal_method == "expire":
        result = await PaymentRequestService.expire(db_session, request=request)
        assert result.state == PaymentRequestState.EXPIRED
    else:
        result = await PaymentRequestService.cancel(db_session, request=request)
        assert result.state == PaymentRequestState.CANCELLED

    assert result.payment_id is None
    total = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.patient_id == gateway_patient.id)
        )
    ).scalar()
    assert total == 0

    # A late "succeeded" confirmation after the terminal transition
    # must never resurrect it into a Payment.
    late_confirmation = make_confirmation(amount=Decimal("500.00"))
    unchanged = await PaymentRequestService.confirm(
        db_session, request=result, confirmation=late_confirmation
    )
    assert unchanged.state == result.state
    assert unchanged.payment_id is None


async def test_terminal_transitions_are_idempotent_no_ops(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    await PaymentRequestService.cancel(db_session, request=request)
    # Calling cancel again (or fail/expire) on an already-terminal
    # request must not raise — never a PaymentRequestTransitionError
    # for a state a retry/race can legitimately hit twice.
    again = await PaymentRequestService.cancel(db_session, request=request)
    assert again.state == PaymentRequestState.CANCELLED


def test_illegal_transition_from_succeeded_back_to_pending_is_rejected():
    from app.modules.payment_gateways.constants import validate_payment_request_transition

    with pytest.raises(PaymentRequestTransitionError):
        validate_payment_request_transition(
            PaymentRequestState.SUCCEEDED, PaymentRequestState.PENDING
        )
