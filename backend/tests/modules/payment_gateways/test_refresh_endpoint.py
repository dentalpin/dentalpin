"""POST /requests/{id}/refresh — manual on-demand status pull.

``PaymentRequestService.get_locked`` (``SELECT ... FOR UPDATE``) is what
makes a webhook delivery landing on the same request while a refresh is
in flight serialize behind it instead of racing on
``confirm()``'s "already succeeded?" check — see the reviewer follow-up
on PR #439/#445 and the docstring on ``get_locked``.

A genuine two-session race isn't reproducible in the single-session
test harness (``AsyncSession`` itself isn't safe for concurrent use —
same rationale as ``tests/modules/india_gst/test_fy_sequence.py``), so
this proves the same invariant the lock protects in production the way
that file does: sequential calls that must resolve to exactly one
Payment, never two.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment_gateways.adapters import GatewayStatusResult
from app.modules.payment_gateways.constants import PaymentRequestState
from app.modules.payment_gateways.service import PaymentRequestService
from app.modules.payments.models import Payment

from .conftest import make_confirmation


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


async def test_refresh_confirms_a_succeeded_request(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_adapter,
    gateway_clinic,
    gateway_patient,
    gateway_user_id,
    auth_headers,
):
    request = await _create_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    fake_adapter.next_status_result = GatewayStatusResult(
        state=str(PaymentRequestState.SUCCEEDED),
        confirmation=make_confirmation(amount=Decimal("500.00")),
    )

    resp = await client.post(
        f"/api/v1/payment_gateways/requests/{request.id}/refresh",
        headers=auth_headers,
        params={"clinic_id": str(gateway_clinic.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == PaymentRequestState.SUCCEEDED

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.patient_id == gateway_patient.id)
        )
    ).scalar()
    assert count == 1


async def test_double_refresh_never_creates_a_second_payment(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_adapter,
    gateway_clinic,
    gateway_patient,
    gateway_user_id,
    auth_headers,
):
    """Two refreshes in a row — an impatient double-click, or a refresh
    racing a webhook that already confirmed the request — must resolve
    to exactly one Payment."""
    request = await _create_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )
    fake_adapter.next_status_result = GatewayStatusResult(
        state=str(PaymentRequestState.SUCCEEDED),
        confirmation=make_confirmation(amount=Decimal("500.00")),
    )

    first = await client.post(
        f"/api/v1/payment_gateways/requests/{request.id}/refresh",
        headers=auth_headers,
        params={"clinic_id": str(gateway_clinic.id)},
    )
    second = await client.post(
        f"/api/v1/payment_gateways/requests/{request.id}/refresh",
        headers=auth_headers,
        params={"clinic_id": str(gateway_clinic.id)},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["payment_id"] == second.json()["data"]["payment_id"]

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.patient_id == gateway_patient.id)
        )
    ).scalar()
    assert count == 1


async def test_refresh_scoped_to_clinic_returns_404_for_another_clinics_request(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_adapter,
    gateway_clinic,
    gateway_patient,
    gateway_user_id,
    auth_headers,
    test_clinic,
):
    """``get_locked`` filters by clinic_id same as the unlocked ``get`` —
    the row lock must never widen what a clinic can reach."""
    request = await _create_request(
        db_session, fake_adapter, gateway_clinic, gateway_patient, gateway_user_id
    )

    resp = await client.post(
        f"/api/v1/payment_gateways/requests/{request.id}/refresh",
        headers=auth_headers,
        params={"clinic_id": str(test_clinic.id)},
    )
    assert resp.status_code == 404
