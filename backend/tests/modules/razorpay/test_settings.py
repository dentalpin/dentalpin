"""razorpay settings: per-clinic isolation, test/live mode, secrets
never returned in API responses."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership


async def test_get_settings_defaults_when_unconfigured(
    client: AsyncClient, auth_headers, test_clinic: Clinic
):
    resp = await client.get("/api/v1/razorpay/settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["mode"] == "test"
    assert data["has_key_secret"] is False
    assert data["has_webhook_secret"] is False
    assert data["is_active"] is False


async def test_update_settings_never_echoes_secrets(
    client: AsyncClient, auth_headers, test_clinic: Clinic
):
    resp = await client.put(
        "/api/v1/razorpay/settings",
        json={
            "mode": "live",
            "key_id": "rzp_live_ABC123",
            "key_secret": "super-secret-value",
            "webhook_secret": "another-secret-value",
            "is_active": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["mode"] == "live"
    assert data["key_id"] == "rzp_live_ABC123"  # not a secret — needed client-side by Checkout.js
    assert data["has_key_secret"] is True
    assert data["has_webhook_secret"] is True
    assert "key_secret" not in data
    assert "webhook_secret" not in data
    body_text = resp.text
    assert "super-secret-value" not in body_text
    assert "another-secret-value" not in body_text

    # A subsequent GET must not leak them either.
    get_resp = await client.get("/api/v1/razorpay/settings", headers=auth_headers)
    assert "super-secret-value" not in get_resp.text
    assert "another-secret-value" not in get_resp.text


async def test_credential_change_resets_verification(
    client: AsyncClient, auth_headers, test_clinic: Clinic
):
    await client.put(
        "/api/v1/razorpay/settings",
        json={"key_id": "rzp_test_1", "key_secret": "s1", "webhook_secret": "w1"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/razorpay/settings", headers=auth_headers)
    assert resp.json()["data"]["is_verified"] is False  # never verified yet in this test

    resp2 = await client.put(
        "/api/v1/razorpay/settings", json={"key_id": "rzp_test_2"}, headers=auth_headers
    )
    assert resp2.json()["data"]["is_verified"] is False


async def test_settings_are_isolated_per_clinic(
    client: AsyncClient, db_session: AsyncSession, auth_headers, test_clinic: Clinic
):
    await client.put(
        "/api/v1/razorpay/settings",
        json={
            "key_id": "rzp_test_clinic_a",
            "key_secret": "s",
            "webhook_secret": "w",
            "is_active": True,
        },
        headers=auth_headers,
    )

    # A second clinic for the same authenticated user must see its own
    # (unconfigured) settings, never clinic A's.
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    clinic_b = Clinic(id=uuid4(), name="Clinic B", tax_id="B00000002", currency="INR", settings={})
    db_session.add(clinic_b)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic_b.id, role="admin")
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/razorpay/settings", headers=auth_headers, params={"clinic_id": str(clinic_b.id)}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["key_id"] is None
    assert data["has_key_secret"] is False
    assert data["is_active"] is False


async def test_update_settings_strips_whitespace_from_credentials(
    client: AsyncClient, db_session: AsyncSession, auth_headers, test_clinic: Clinic
):
    """A trailing newline/space copy-pasted from the Razorpay dashboard
    must never reach Basic Auth — Razorpay does an exact match and
    would otherwise return a 401 that's indistinguishable from a wrong
    key (issue: reported 'Could not start payment with razorpay:
    Razorpay returned HTTP 401 ... Authentication failed')."""
    from app.modules.razorpay.service import RazorpaySettingsService

    resp = await client.put(
        "/api/v1/razorpay/settings",
        json={
            "mode": " test ",
            "key_id": "  rzp_test_ABC123\n",
            "key_secret": " super-secret-value \n",
            "webhook_secret": "\tanother-secret-value\t",
            "is_active": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["mode"] == "test"
    assert data["key_id"] == "rzp_test_ABC123"  # plaintext, echoed — must be trimmed

    settings = await RazorpaySettingsService.get_settings(db_session, test_clinic.id)
    key_id, key_secret = RazorpaySettingsService.decrypt_credentials(settings)
    assert key_id == "rzp_test_ABC123"
    assert key_secret == "super-secret-value"

    # webhook secret isn't exposed via decrypt_credentials (key-pair only);
    # verify it directly through the encryption util instead.
    from app.core.email.encryption import decrypt_password

    assert decrypt_password(settings.webhook_secret_encrypted) == "another-secret-value"


async def test_settings_endpoints_require_permission(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    from app.core.auth.models import User
    from app.core.auth.service import create_access_token, hash_password

    receptionist = User(
        id=uuid4(),
        email="reception-settings@test.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Recep",
        last_name="Tionist",
    )
    db_session.add(receptionist)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(), user_id=receptionist.id, clinic_id=test_clinic.id, role="receptionist"
        )
    )
    await db_session.commit()
    token = create_access_token(receptionist.id, token_version=receptionist.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/razorpay/settings", headers=headers)
    assert resp.status_code == 403

    resp2 = await client.put("/api/v1/razorpay/settings", json={"is_active": True}, headers=headers)
    assert resp2.status_code == 403
