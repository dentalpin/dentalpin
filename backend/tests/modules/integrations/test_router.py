"""integrations router: subscription CRUD, secret-once, permission gate."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.models import WebhookDelivery

BASE = "/api/v1/integrations/webhooks/subscriptions"


@pytest.mark.asyncio
async def test_create_returns_secret_once(client: AsyncClient, auth_headers, test_clinic):
    resp = await client.post(
        BASE,
        json={"target_url": "https://example.com/hook", "event_types": ["patient.created"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert "secret" in body and len(body["secret"]) > 20
    subscription_id = body["id"]

    # List must never leak the secret.
    listed = await client.get(BASE, headers=auth_headers)
    assert listed.status_code == 200
    for row in listed.json()["data"]:
        assert "secret" not in row

    # Re-fetching via list must not carry the plaintext either, even for
    # the same subscription just created.
    same = next(r for r in listed.json()["data"] if r["id"] == subscription_id)
    assert "secret" not in same


@pytest.mark.asyncio
async def test_unsupported_event_type_rejected(client: AsyncClient, auth_headers, test_clinic):
    resp = await client.post(
        BASE,
        json={"target_url": "https://example.com/hook", "event_types": ["invoice.issued"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unsafe_target_url_rejected(client: AsyncClient, auth_headers, test_clinic):
    """SSRF guard (url_safety.py) runs on the create/update path — a
    private-network target_url must never reach the DB."""
    resp = await client.post(
        BASE,
        json={
            "target_url": "https://169.254.169.254/latest/meta-data/",
            "event_types": ["patient.created"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422

    resp_http = await client.post(
        BASE,
        json={"target_url": "http://example.com/hook", "event_types": ["patient.created"]},
        headers=auth_headers,
    )
    assert resp_http.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_roundtrip(client: AsyncClient, auth_headers, test_clinic):
    created = await client.post(
        BASE,
        json={"target_url": "https://example.com/hook", "event_types": ["patient.created"]},
        headers=auth_headers,
    )
    subscription_id = created.json()["data"]["id"]

    updated = await client.patch(
        f"{BASE}/{subscription_id}", json={"is_active": False}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["is_active"] is False

    deleted = await client.delete(f"{BASE}/{subscription_id}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = await client.patch(
        f"{BASE}/{subscription_id}", json={"is_active": True}, headers=auth_headers
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_update_can_clear_description_to_null(client: AsyncClient, auth_headers, test_clinic):
    """Regression test: `description` must actually be clearable — the
    old `update_subscription` used `data.get(field) is not None`, which
    could never distinguish "not sent" from "sent as null" and so could
    never clear it."""
    created = await client.post(
        BASE,
        json={
            "target_url": "https://example.com/hook",
            "event_types": ["patient.created"],
            "description": "Zapier prod",
        },
        headers=auth_headers,
    )
    subscription_id = created.json()["data"]["id"]
    assert created.json()["data"]["description"] == "Zapier prod"

    cleared = await client.patch(
        f"{BASE}/{subscription_id}", json={"description": None}, headers=auth_headers
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["description"] is None


@pytest.mark.asyncio
async def test_non_admin_role_forbidden(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic
):
    from uuid import uuid4

    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    receptionist = User(
        email="reception@example.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Recep",
        last_name="Tionist",
    )
    db_session.add(receptionist)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=receptionist.id,
            clinic_id=test_clinic.id,
            role="receptionist",
        )
    )
    await db_session.commit()

    token = create_access_token(receptionist.id, token_version=receptionist.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_clinic_subscription_not_visible(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic
):
    from uuid import uuid4

    from app.core.auth.models import Clinic

    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B87654321",
        address={"street": "Other St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    from app.core.email.encryption import encrypt_password
    from app.modules.integrations.models import WebhookSubscription

    other_sub = WebhookSubscription(
        clinic_id=other_clinic.id,
        target_url="https://example.com/other",
        event_types=["patient.created"],
        secret_encrypted=encrypt_password("s"),
    )
    db_session.add(other_sub)
    await db_session.commit()

    resp = await client.patch(
        f"{BASE}/{other_sub.id}", json={"is_active": False}, headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_subscription_with_deliveries(
    client: AsyncClient, auth_headers, test_clinic, db_session: AsyncSession
):
    """A subscription that has fired once used to fail the DELETE on the
    webhook_deliveries FK with a 500 (#750)."""
    created = await client.post(
        BASE,
        json={"target_url": "https://example.com/hook", "event_types": ["patient.created"]},
        headers=auth_headers,
    )
    subscription_id = created.json()["data"]["id"]
    for status in ("sent", "queued"):
        db_session.add(
            WebhookDelivery(
                subscription_id=subscription_id,
                clinic_id=test_clinic.id,
                event_type="patient.created",
                payload={},
                status=status,
            )
        )
    await db_session.commit()

    deleted = await client.delete(f"{BASE}/{subscription_id}", headers=auth_headers)
    assert deleted.status_code == 204, deleted.text
    remaining = await db_session.scalar(
        select(func.count())
        .select_from(WebhookDelivery)
        .where(WebhookDelivery.subscription_id == subscription_id)
    )
    assert remaining == 0
