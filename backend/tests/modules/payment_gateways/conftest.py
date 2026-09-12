"""Shared fixtures for payment_gateways tests.

``FakeAdapter`` is a fully in-memory ``GatewayAdapter`` implementation
— no network, deterministic, inspectable calls — registered into the
real ``gateway_registry`` for the duration of a test. This is what
lets the state-machine/service tests exercise the exact same code
paths a real provider module would hit, without needing live
credentials (mirrors how ``notifications`` tests would fake a
``ChannelAdapter``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payment_gateways.adapters import (
    GatewayCheckoutResult,
    GatewayConfirmation,
    GatewayRefundInitResult,
    GatewayRefundStatusResult,
    GatewayStatusResult,
    gateway_registry,
)
from app.modules.payment_gateways.constants import GatewayRefundState


class FakeAdapter:
    """Deterministic in-memory adapter. Configure ``next_*`` /
    ``*_should_raise`` before calling into the service under test."""

    provider_key = "fake"
    supported_methods = ("upi", "qr", "card", "payment_link")

    def __init__(self) -> None:
        self.unsupported_clinics: set[UUID] = set()
        self.initiate_calls: list = []
        self.refund_calls: list = []
        self._order_seq = 0
        self._refund_seq = 0
        self.next_checkout: GatewayCheckoutResult | None = None
        self.initiate_should_raise: Exception | None = None
        self.refund_should_raise: Exception | None = None
        self.next_refund_result: GatewayRefundInitResult | None = None

    async def supports(self, db, clinic_id) -> bool:
        return clinic_id not in self.unsupported_clinics

    async def initiate_payment(self, db, *, request, customer) -> GatewayCheckoutResult:
        self.initiate_calls.append((request.id, customer))
        if self.initiate_should_raise:
            raise self.initiate_should_raise
        if self.next_checkout is not None:
            return self.next_checkout
        self._order_seq += 1
        return GatewayCheckoutResult(
            provider_reference=f"fake_order_{self._order_seq}",
            method=request.requested_method,
            checkout_payload={"fake": True},
        )

    async def verify_payment_status(self, db, *, request) -> GatewayStatusResult:
        return GatewayStatusResult(state=request.state)

    def verify_webhook_signature(self, *, raw_body, headers, secret) -> bool:
        return True

    async def parse_webhook_event(self, db, *, clinic_id, payload):
        return None

    async def initiate_refund(self, db, *, refund_request) -> GatewayRefundInitResult:
        self.refund_calls.append(refund_request.id)
        if self.refund_should_raise:
            raise self.refund_should_raise
        if self.next_refund_result is not None:
            return self.next_refund_result
        self._refund_seq += 1
        return GatewayRefundInitResult(
            provider_refund_reference=f"fake_refund_{self._refund_seq}",
            state=str(GatewayRefundState.PROCESSING),
        )

    async def refresh_refund_status(self, db, *, refund_request) -> GatewayRefundStatusResult:
        return GatewayRefundStatusResult(state=refund_request.state)


def make_confirmation(
    provider_payment_reference: str = "fake_pay_1",
    *,
    amount: Decimal,
    currency: str = "INR",
    method: str = "upi",
) -> GatewayConfirmation:
    return GatewayConfirmation(
        provider_payment_reference=provider_payment_reference,
        confirmed_method=method,
        amount=amount,
        currency=currency,
        captured_at=datetime.now(UTC),
    )


@pytest.fixture
def fake_adapter():
    adapter = FakeAdapter()
    gateway_registry.register(adapter)
    yield adapter
    gateway_registry.unregister("fake")


@pytest_asyncio.fixture
async def gateway_clinic(
    db_session: AsyncSession, auth_headers: dict, client: AsyncClient
) -> Clinic:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Gateway Test Clinic",
        tax_id="B99999999",
        currency="INR",
        settings={},
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    await db_session.commit()
    return clinic


@pytest_asyncio.fixture
async def gateway_patient(db_session: AsyncSession, gateway_clinic: Clinic) -> Patient:
    patient = Patient(
        id=uuid4(),
        clinic_id=gateway_clinic.id,
        first_name="Priya",
        last_name="Sharma",
        email="priya@test.com",
        phone="+919876543210",
    )
    db_session.add(patient)
    await db_session.commit()
    return patient


@pytest_asyncio.fixture
async def gateway_user_id(auth_headers: dict, client: AsyncClient) -> UUID:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    return UUID(me.json()["data"]["user"]["id"])
