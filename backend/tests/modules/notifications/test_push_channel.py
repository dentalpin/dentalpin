"""notifications WebPush channel (T6): subscriptions, adapter, resolver, endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
    # NOTE: no unregister — the adapter registers from on_activate in
    # production; removing it here would break test ordering.


@pytest.fixture()
def vapid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_SUBJECT", "mailto:test@example.com")


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
    from cryptography.hazmat.primitives import serialization

    pem = settings.DENTALPIN_VAPID_PRIVATE_KEY
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    nums = key.public_key().public_numbers()
    raw = b"\x04" + nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
    assert vapid_public_key() == base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_vapid_public_key_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", "")
    assert vapid_public_key() is None


# --- Adapter unit -----------------------------------------------------------


def _stub_webpush(monkeypatch: pytest.MonkeyPatch, fail_with_status: int | None = None):
    """Patch the top-level async import (hard dependency, no sys.modules stub)."""
    import types

    from pywebpush import WebPushException

    import app.modules.notifications.channels.push_adapter as adapter_module

    calls: list[dict] = []

    async def webpush_async(subscription_info, **kwargs):
        calls.append({"subscription_info": subscription_info, **kwargs})
        if fail_with_status is not None:
            response = types.SimpleNamespace(status=fail_with_status, headers={})
            raise WebPushException("gone", response=response)
        return types.SimpleNamespace(status=201, headers={})

    monkeypatch.setattr(adapter_module, "webpush_async", webpush_async)
    return calls


@pytest.mark.asyncio
async def test_adapter_supports_only_when_configured(
    test_clinic: Clinic, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = PushAdapter()
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", "")
    assert await adapter.supports(db_session, test_clinic.id) is False
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
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
    assert calls[0]["ttl"] == 24 * 3600
    assert calls[0]["timeout"] == 10.0
    # The VAPID auth must be a parsed instance, never the raw PEM
    # string (pywebpush deserializes strings as base64url and fails).
    from py_vapid import Vapid

    assert isinstance(calls[0]["vapid_private_key"], Vapid)


@pytest.mark.asyncio
async def test_adapter_supports_depends_on_parsable_key(
    test_clinic: Clinic, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = PushAdapter()
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", "not-a-key")
    assert await adapter.supports(db_session, test_clinic.id) is False


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


@pytest.mark.asyncio
async def test_adapter_truncation_keeps_accented_body_under_cap(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    vapid_env: None,
) -> None:
    """Truncation must measure wire bytes: re-serialising with ASCII
    escaping would inflate an accented body past the cap (413s)."""
    import json

    from app.modules.notifications.channels.base import OutboundMessage
    from app.modules.notifications.channels.push_adapter import (
        PUSH_MAX_BYTES,
        _fit_payload,
    )

    body = "ñandú " * 700
    payload = json.dumps({"title": "t", "body": body}, ensure_ascii=False)
    assert len(payload.encode("utf-8")) > PUSH_MAX_BYTES
    assert len(_fit_payload(payload).encode("utf-8")) <= PUSH_MAX_BYTES

    calls = _stub_webpush(monkeypatch)
    await _subscribe(db_session, test_clinic, test_patient)
    result = await PushAdapter().send(
        db_session,
        OutboundMessage(
            channel=Channel.PUSH,
            to_address="push",
            clinic_id=test_clinic.id,
            template_key="x",
            patient_id=test_patient.id,
            subject="t",
            body_text=body,
        ),
    )
    assert result.status == SendStatus.SENT
    assert len(calls[0]["data"].encode("utf-8")) <= PUSH_MAX_BYTES


@pytest.mark.asyncio
async def test_adapter_signs_through_real_webpush_path(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    vapid_env: None,
) -> None:
    """Real webpush_async with only the HTTP transport stubbed.

    Exercises the isinstance(vapid_private_key, Vapid01) branch and
    Vapid.sign end to end — the path that broke when a raw PEM string
    was passed (pywebpush deserializes strings as base64url).
    """
    import base64
    import types

    from cryptography.hazmat.primitives.asymmetric import ec

    from app.modules.notifications.channels.base import OutboundMessage

    key = ec.generate_private_key(ec.SECP256R1())
    nums = key.public_key().public_numbers()
    raw_point = b"\x04" + nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
    await PushSubscriptionService.subscribe(
        db_session,
        test_clinic.id,
        test_patient.id,
        "https://push.example/sign-path",
        {
            "p256dh": base64.urlsafe_b64encode(raw_point).rstrip(b"=").decode(),
            "auth": base64.urlsafe_b64encode(b"\x01" * 16).rstrip(b"=").decode(),
        },
    )
    seen: dict = {}

    async def fake_send_async(self, data, headers, **kwargs):
        seen.update(data=data, headers=headers)
        return types.SimpleNamespace(status=201)

    monkeypatch.setattr("pywebpush.WebPusher.send_async", fake_send_async)
    result = await PushAdapter().send(
        db_session,
        OutboundMessage(
            channel=Channel.PUSH,
            to_address="push",
            clinic_id=test_clinic.id,
            template_key="x",
            patient_id=test_patient.id,
            subject="t",
            body_text="Hola",
        ),
    )
    assert result.status == SendStatus.SENT
    assert seen["headers"]["Authorization"].startswith("vapid t=")


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
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", "")
    missing = await client.get("/api/v1/notifications/push/vapid-public-key", headers=auth_headers)
    assert missing.status_code == 503

    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
    present = await client.get("/api/v1/notifications/push/vapid-public-key", headers=auth_headers)
    assert present.status_code == 200
    assert len(present.json()["data"]["public_key"]) > 80


# --- Patient subscribe flow + hardening --------------------------------------


@pytest.mark.asyncio
async def test_non_https_endpoint_422s(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, test_patient: Patient
) -> None:
    response = await client.post(
        "/api/v1/notifications/push/subscriptions",
        json={
            "patient_id": str(test_patient.id),
            "endpoint": "http://10.0.0.5/worker",
            "keys": {"p256dh": "p", "auth": "a"},
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_token_flow(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
    minted = await client.post(
        "/api/v1/notifications/push/subscribe-tokens",
        json={"patient_id": str(test_patient.id)},
        headers=auth_headers,
    )
    assert minted.status_code == 201, minted.text
    token = minted.json()["data"]["token"]

    # Validate without consuming.
    validated = await client.get(f"/api/v1/notifications/public/push/subscribe/{token}")
    assert validated.status_code == 200
    assert validated.json()["data"]["valid"] is True
    assert len(validated.json()["data"]["public_key"]) > 80

    # Redeem with the browser subscription.
    redeemed = await client.post(
        f"/api/v1/notifications/public/push/subscribe/{token}",
        json={
            "endpoint": "https://push.example/patient-1",
            "keys": {"p256dh": "p", "auth": "a"},
        },
    )
    assert redeemed.status_code == 201, redeemed.text
    assert redeemed.json()["data"] == {"subscribed": True}

    # Single use: second redeem 404s, and so does validation now.
    assert (
        await client.post(
            f"/api/v1/notifications/public/push/subscribe/{token}",
            json={
                "endpoint": "https://push.example/patient-2",
                "keys": {"p256dh": "p", "auth": "a"},
            },
        )
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/notifications/public/push/subscribe/{token}")
    ).status_code == 404

    # Unknown token 404s.
    assert (
        await client.get(f"/api/v1/notifications/public/push/subscribe/{uuid4()}")
    ).status_code == 404


@pytest.mark.asyncio
async def test_public_redeem_rejects_http_endpoint(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DENTALPIN_VAPID_PRIVATE_KEY", _test_private_pem())
    minted = await client.post(
        "/api/v1/notifications/push/subscribe-tokens",
        json={"patient_id": str(test_patient.id)},
        headers=auth_headers,
    )
    token = minted.json()["data"]["token"]
    bad = await client.post(
        f"/api/v1/notifications/public/push/subscribe/{token}",
        json={
            "endpoint": "http://10.0.0.5/worker",
            "keys": {"p256dh": "p", "auth": "a"},
        },
    )
    assert bad.status_code == 422
    # The rejected redeem must not burn the token.
    again = await client.get(f"/api/v1/notifications/public/push/subscribe/{token}")
    assert again.status_code == 200


@pytest.mark.asyncio
async def test_cross_clinic_push_isolation(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
) -> None:
    from app.core.auth.models import Clinic as ClinicModel

    other = ClinicModel(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()

    await _subscribe(db_session, test_clinic, test_patient)
    # Another clinic sees nothing and deletes nothing.
    assert (
        await PushSubscriptionService.list_for_patient(db_session, other.id, test_patient.id) == []
    )
    assert (
        await PushSubscriptionService.unsubscribe(
            db_session,
            other.id,
            (
                await PushSubscriptionService.list_for_patient(
                    db_session, test_clinic.id, test_patient.id
                )
            )[0].id,
        )
        is False
    )


@pytest.mark.asyncio
async def test_cross_clinic_push_http_404s(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    from app.core.auth.models import Clinic as ClinicModel

    other = ClinicModel(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999992",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    other_patient = Patient(
        clinic_id=other.id, first_name="Otra", last_name="Clinica", status="active"
    )
    db_session.add(other_patient)
    await db_session.commit()

    # Other clinic's patient is not referenceable from here.
    assert (
        await client.post(
            "/api/v1/notifications/push/subscriptions",
            json={
                "patient_id": str(other_patient.id),
                "endpoint": "https://push.example/x",
                "keys": {"p256dh": "p", "auth": "a"},
            },
            headers=auth_headers,
        )
    ).status_code == 404

    # B's subscription row is invisible and untouchable from A: without the
    # clinic filter the GET below would list it and the DELETE would 204.
    other_sub = await _subscribe(
        db_session, other, other_patient, endpoint="https://push.example/sub-b"
    )
    await db_session.commit()
    assert (
        await client.get(
            "/api/v1/notifications/push/subscriptions",
            params={"patient_id": str(other_patient.id)},
            headers=auth_headers,
        )
    ).json()["data"] == []
    assert (
        await client.delete(
            f"/api/v1/notifications/push/subscriptions/{other_sub.id}",
            headers=auth_headers,
        )
    ).status_code == 404

    # A's own subscription row deletes normally through the A-scoped path.
    sub = await _subscribe(db_session, test_clinic, test_patient)
    await db_session.commit()
    assert (
        await client.delete(
            f"/api/v1/notifications/push/subscriptions/{sub.id}", headers=auth_headers
        )
    ).status_code == 204


@pytest.mark.asyncio
async def test_pruning_never_touches_other_clinic(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
    vapid_env: None,
) -> None:
    from app.core.auth.models import Clinic as ClinicModel
    from app.modules.notifications.channels.base import OutboundMessage

    other = ClinicModel(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999993",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()

    # Same endpoint string, two clinic scopes = two rows.
    await _subscribe(db_session, test_clinic, test_patient)
    other_patient = Patient(
        clinic_id=other.id, first_name="Otra", last_name="Clinica", status="active"
    )
    db_session.add(other_patient)
    await db_session.commit()
    await PushSubscriptionService.subscribe(
        db_session,
        other.id,
        other_patient.id,
        "https://push.example/sub-1",
        {"p256dh": "p256dh-key", "auth": "auth-secret"},
    )
    await db_session.commit()

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
    assert (
        await PushSubscriptionService.list_for_patient(db_session, test_clinic.id, test_patient.id)
        == []
    )
    # B's row survives A's prune.
    assert (
        len(await PushSubscriptionService.list_for_patient(db_session, other.id, other_patient.id))
        == 1
    )
