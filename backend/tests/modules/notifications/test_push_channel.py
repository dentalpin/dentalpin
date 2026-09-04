"""notifications WebPush channel (T6): subscriptions, adapter, resolver, endpoints."""

from __future__ import annotations

import sys
import types
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.channels import Channel, SendStatus, channel_registry
from app.modules.notifications.channels.push_adapter import PushAdapter
from app.modules.notifications.channels.vapid import vapid_public_key
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import PushSubscription
from app.modules.notifications.push import PushSubscriptionService
from app.modules.patients.models import Patient


@pytest_asyncio.fixture
async def push_adapter():
    adapter = PushAdapter()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("webpush")


@pytest.fixture()
def vapid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
    monkeypatch.setenv("DENTALPIN_VAPID_SUBJECT", "mailto:test@example.com")


def _test_private_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


async def _subscribe(
    db: AsyncSession, clinic: Clinic, patient: Patient, endpoint: str = "https://push.example/sub-1"
) -> PushSubscription:
    return await PushSubscriptionService.subscribe(
        db,
        clinic.id,
        patient.id,
        endpoint,
        {"p256dh": "p256dh-key", "auth": "auth-secret"},
        user_agent="test-browser",
    )


# --- VAPID helper -----------------------------------------------------------


def test_vapid_public_key_derivation(vapid_env: None) -> None:
    import base64

    # Re-derive independently: the helper must match the raw uncompressed point.
    import os

    from cryptography.hazmat.primitives import serialization

    pem = os.environ["DENTALPIN_VAPID_PRIVATE_KEY"]
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    nums = key.public_key().public_numbers()
    raw = b"\x04" + nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
    assert vapid_public_key() == base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_vapid_public_key_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DENTALPIN_VAPID_PRIVATE_KEY", raising=False)
    assert vapid_public_key() is None


# --- Adapter unit -----------------------------------------------------------


def _stub_webpush(monkeypatch: pytest.MonkeyPatch, fail_with_status: int | None = None):
    calls: list[dict] = []
    module = types.ModuleType("pywebpush")

    class StubPushError(Exception):
        def __init__(self, message: str = "", response=None) -> None:
            super().__init__(message)
            self.response = response

    def webpush(subscription_info, data, vapid_private_key, vapid_claims):
        calls.append(
            {
                "subscription_info": subscription_info,
                "data": data,
                "vapid_claims": vapid_claims,
            }
        )
        if fail_with_status is not None:
            response = types.SimpleNamespace(status_code=fail_with_status)
            raise StubPushError("gone", response=response)
        return types.SimpleNamespace(status_code=201)

    module.WebPushException = StubPushError
    module.webpush = webpush
    monkeypatch.setitem(sys.modules, "pywebpush", module)
    return calls


@pytest.mark.asyncio
async def test_adapter_supports_only_when_configured(
    test_clinic: Clinic, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = PushAdapter()
    monkeypatch.delenv("DENTALPIN_VAPID_PRIVATE_KEY", raising=False)
    assert await adapter.supports(db_session, test_clinic.id) is False
    monkeypatch.setenv("DENTALPIN_VAPID_PRIVATE_KEY", "anything")
    assert await adapter.supports(db_session, test_clinic.id) is True


@pytest.mark.asyncio
async def test_adapter_sends_to_subscriptions(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    vapid_env: None,
) -> None:
    from app.modules.notifications.channels.base import OutboundMessage

    await _subscribe(db_session, test_clinic, test_patient)
    calls = _stub_webpush(monkeypatch)
    result = await PushAdapter().send(
        db_session,
        OutboundMessage(
            channel=Channel.PUSH,
            to_address="push",
            clinic_id=test_clinic.id,
            template_key="appointment_reminder",
            patient_id=test_patient.id,
            subject="Recordatorio",
            body_text="Su cita es mañana",
        ),
    )
    assert result.status == SendStatus.SENT
    assert len(calls) == 1
    import json

    payload = json.loads(calls[0]["data"])
    assert payload == {"title": "Recordatorio", "body": "Su cita es mañana"}
    assert calls[0]["vapid_claims"] == {"sub": "mailto:test@example.com"}


@pytest.mark.asyncio
async def test_adapter_prunes_dead_subscriptions(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    vapid_env: None,
) -> None:
    from app.modules.notifications.channels.base import OutboundMessage

    await _subscribe(db_session, test_clinic, test_patient)
    _stub_webpush(monkeypatch, fail_with_status=410)
    result = await PushAdapter().send(
        db_session,
        OutboundMessage(
            channel=Channel.PUSH,
            to_address="push",
            clinic_id=test_clinic.id,
            template_key="appointment_reminder",
            patient_id=test_patient.id,
            body_text="Hola",
        ),
    )
    assert result.status == SendStatus.FAILED
    remaining = await PushSubscriptionService.list_for_patient(
        db_session, test_clinic.id, test_patient.id
    )
    assert remaining == []


@pytest.mark.asyncio
async def test_adapter_skips_empty_body_and_missing_subscriptions(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    vapid_env: None,
) -> None:
    from app.modules.notifications.channels.base import OutboundMessage

    calls = _stub_webpush(monkeypatch)
    adapter = PushAdapter()
    empty = await adapter.send(
        db_session,
        OutboundMessage(
            channel=Channel.PUSH,
            to_address="push",
            clinic_id=test_clinic.id,
            template_key="x",
            patient_id=test_patient.id,
            body_text="  ",
        ),
    )
    assert empty.status == SendStatus.SKIPPED
    missing = await adapter.send(
        db_session,
        OutboundMessage(
            channel=Channel.PUSH,
            to_address="push",
            clinic_id=test_clinic.id,
            template_key="x",
            patient_id=test_patient.id,
            body_text="Hola",
        ),
    )
    assert missing.status == SendStatus.FAILED
    assert calls == []


# --- Resolver + consent -----------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_resolves_push_with_subscription(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    push_adapter,
    vapid_env: None,
) -> None:
    await _subscribe(db_session, test_clinic, test_patient)
    msg = await NotificationGateway.enqueue(
        db_session,
        test_clinic.id,
        "appointment_reminder",
        context={},
        patient_id=test_patient.id,
        channels=["push"],
        body_text="Su cita es mañana",
    )
    assert msg is not None
    assert msg.channel == "push"


@pytest.mark.asyncio
async def test_enqueue_skips_push_without_subscription_or_opt_out(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    push_adapter,
    vapid_env: None,
) -> None:
    from app.modules.notifications.service import NotificationService

    # No subscription → no viable channel.
    skipped = await NotificationGateway.enqueue(
        db_session,
        test_clinic.id,
        "appointment_reminder",
        context={},
        patient_id=test_patient.id,
        channels=["push"],
        body_text="Hola",
    )
    assert skipped is not None
    assert skipped.status == "skipped"

    # Subscription + explicit opt-out → skipped too.
    await _subscribe(db_session, test_clinic, test_patient)
    await NotificationService.update_patient_preferences(
        db_session, test_clinic.id, test_patient.id, {"push_enabled": False}
    )
    opted_out = await NotificationGateway.enqueue(
        db_session,
        test_clinic.id,
        "appointment_reminder",
        context={},
        patient_id=test_patient.id,
        channels=["push"],
        body_text="Hola",
    )
    assert opted_out is not None
    assert opted_out.status == "skipped"


# --- HTTP surface -----------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_endpoints_round_trip(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, test_patient: Patient
) -> None:
    create = await client.post(
        "/api/v1/notifications/push/subscriptions",
        json={
            "patient_id": str(test_patient.id),
            "endpoint": "https://push.example/sub-9",
            "keys": {"p256dh": "p", "auth": "a"},
        },
        headers=auth_headers,
    )
    assert create.status_code == 201, create.text
    sub_id = create.json()["data"]["id"]

    # Re-subscribing the same endpoint refreshes in place (upsert).
    again = await client.post(
        "/api/v1/notifications/push/subscriptions",
        json={
            "patient_id": str(test_patient.id),
            "endpoint": "https://push.example/sub-9",
            "keys": {"p256dh": "p2", "auth": "a2"},
        },
        headers=auth_headers,
    )
    assert again.status_code == 201
    assert again.json()["data"]["id"] == sub_id

    listing = await client.get(
        f"/api/v1/notifications/push/subscriptions?patient_id={test_patient.id}",
        headers=auth_headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1

    delete = await client.delete(
        f"/api/v1/notifications/push/subscriptions/{sub_id}", headers=auth_headers
    )
    assert delete.status_code == 204
    assert (
        await client.delete(
            f"/api/v1/notifications/push/subscriptions/{sub_id}", headers=auth_headers
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_subscribe_unknown_patient_404s(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.post(
        "/api/v1/notifications/push/subscriptions",
        json={
            "patient_id": str(uuid4()),
            "endpoint": "https://push.example/nope",
            "keys": {"p256dh": "p", "auth": "a"},
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_vapid_public_key_endpoint(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DENTALPIN_VAPID_PRIVATE_KEY", raising=False)
    missing = await client.get("/api/v1/notifications/push/vapid-public-key", headers=auth_headers)
    assert missing.status_code == 503

    monkeypatch.setenv("DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
    present = await client.get("/api/v1/notifications/push/vapid-public-key", headers=auth_headers)
    assert present.status_code == 200
    assert len(present.json()["data"]["public_key"]) > 80
