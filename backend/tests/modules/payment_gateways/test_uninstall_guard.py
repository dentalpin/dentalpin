"""payment_gateways uninstall guard: refuses to remove the module while
any ``PaymentRequest``/``GatewayRefundRequest`` is still in a
non-terminal state — see ``PaymentGatewaysModule.uninstall()`` and the
module CLAUDE.md's "Lifecycle" section. Removing the module while a
checkout or refund is in flight would orphan it: the provider-side
attempt (and the patient waiting on it) would have nothing left to
resolve into once the tables are gone.

Uses ``FakeAdapter`` (conftest) — no network, no real provider.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.payment_gateways import PaymentGatewaysModule
from app.modules.payment_gateways.service import (
    GatewayRefundService,
    PaymentRequestService,
)
from app.modules.payments.service import PaymentService

from .conftest import make_confirmation


class _Ctx:
    """Minimal stand-in for ``ModuleContext`` — ``uninstall()`` only
    reads ``ctx.db`` (mirrors the ``_Ctx`` stub in
    ``test_registry.py::test_razorpay_module_uninstall_unregisters_adapter``)."""

    def __init__(self, db) -> None:
        self.db = db


async def _create_request(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    return await PaymentRequestService.create_and_initiate(
        db_session,
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


async def test_uninstall_blocked_by_in_flight_payment_request(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    await _create_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    # create_and_initiate leaves the request AWAITING_CUSTOMER_ACTION —
    # non-terminal — with FakeAdapter.

    with pytest.raises(RuntimeError, match="still in flight"):
        await PaymentGatewaysModule().uninstall(_Ctx(db=db_session))


async def test_uninstall_blocked_by_in_flight_refund_request(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    confirmed = await PaymentRequestService.confirm(
        db_session, request=request, confirmation=make_confirmation(amount=Decimal("500.00"))
    )
    payment = await PaymentService.get(db_session, gateway_clinic.id, confirmed.payment_id)

    await GatewayRefundService.request_refund(
        db_session,
        clinic_id=gateway_clinic.id,
        payment=payment,
        payment_request=confirmed,
        amount=Decimal("100.00"),
        reason_code="duplicate",
        reason_note=None,
        requested_by=gateway_user_id,
    )
    # FakeAdapter's default refund result leaves this PROCESSING — the
    # PaymentRequest itself is already SUCCEEDED (terminal), so this
    # proves the refund half of the guard independently of the request
    # half covered above.

    with pytest.raises(RuntimeError, match="still in flight"):
        await PaymentGatewaysModule().uninstall(_Ctx(db=db_session))


async def test_uninstall_succeeds_once_all_requests_are_terminal(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await _create_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    await PaymentRequestService.cancel(db_session, request=request)

    # No non-terminal rows left -> uninstall proceeds without raising.
    await PaymentGatewaysModule().uninstall(_Ctx(db=db_session))
