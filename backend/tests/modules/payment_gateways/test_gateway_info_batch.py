"""POST /payments/gateway-info/batch — one call for a page of the
payments list instead of one ``/gateway-info`` round trip per
gateway-collected row (#439/#445 review follow-up).

Uses ``FakeAdapter`` (conftest) — no network, no real provider.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment_gateways.service import PaymentRequestService

from .conftest import make_confirmation


async def _confirmed_request(
    db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
):
    request = await PaymentRequestService.create_and_initiate(
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
    return await PaymentRequestService.confirm(
        db_session, request=request, confirmation=make_confirmation(amount=Decimal("500.00"))
    )


async def test_batch_returns_info_only_for_gateway_collected_payments(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_adapter,
    gateway_clinic,
    gateway_patient,
    gateway_user_id,
    auth_headers,
):
    confirmed = await _confirmed_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    manual_payment_id = str(uuid4())  # no PaymentRequest behind it — a manually-recorded payment

    resp = await client.post(
        "/api/v1/payment_gateways/payments/gateway-info/batch",
        json={"payment_ids": [str(confirmed.payment_id), manual_payment_id]},
        headers=auth_headers,
        params={"clinic_id": str(gateway_clinic.id)},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert str(confirmed.payment_id) in data
    assert data[str(confirmed.payment_id)]["request"]["state"] == "succeeded"
    assert data[str(confirmed.payment_id)]["request"]["payment_id"] == str(confirmed.payment_id)
    # Manually-recorded payment id: absent, same as the single endpoint's
    # `request: null` — never a 404 or an error for a normal payment.
    assert manual_payment_id not in data


async def test_batch_is_scoped_to_the_requesting_clinic(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_adapter,
    gateway_clinic,
    gateway_patient,
    gateway_user_id,
    auth_headers,
    test_clinic,
):
    """A payment id from another clinic must never leak gateway info,
    even if a caller in a different clinic happens to guess/reuse the id."""
    confirmed = await _confirmed_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )

    resp = await client.post(
        "/api/v1/payment_gateways/payments/gateway-info/batch",
        json={"payment_ids": [str(confirmed.payment_id)]},
        headers=auth_headers,
        params={"clinic_id": str(test_clinic.id)},  # different clinic, same user
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {}


async def test_batch_rejects_more_than_the_page_size_cap(
    client: AsyncClient,
    gateway_clinic,
    auth_headers,
):
    too_many = [str(uuid4()) for _ in range(101)]
    resp = await client.post(
        "/api/v1/payment_gateways/payments/gateway-info/batch",
        json={"payment_ids": too_many},
        headers=auth_headers,
        params={"clinic_id": str(gateway_clinic.id)},
    )
    assert resp.status_code == 422
