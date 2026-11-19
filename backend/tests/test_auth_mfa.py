"""Staff TOTP protects session issuance and preserves clinic isolation."""

from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import func, select

from app.config import settings
from app.core.auth import mfa
from app.core.auth.models import (
    Clinic,
    ClinicMembership,
    MfaAuditEntry,
    User,
    UserMfaChallenge,
    UserMfaRecoveryCode,
    UserMfaTotp,
)
from app.core.auth.service import create_invite_token, hash_password

AUTH = "/api/v1/auth"
POLICY = f"{AUTH}/clinic/settings/mfa"
PASSWORD = "TestPass1234"
EMAIL = "test@example.com"


@pytest.fixture
def key(monkeypatch):
    value = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "MFA_ENCRYPTION_KEY", SecretStr(value))
    monkeypatch.setattr(settings, "MFA_PREVIOUS_ENCRYPTION_KEY", None)
    return value


@pytest.fixture
def clock(monkeypatch):
    class FixedClock:
        now_value = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

        @classmethod
        def now(cls, tz):
            return cls.now_value.astimezone(tz)

    monkeypatch.setattr(mfa, "datetime", FixedClock)
    return FixedClock


async def policy(client, headers, mode, roles=(), clinic_id=None):
    response = await client.put(
        POLICY,
        headers=headers,
        json={"mode": mode, "roles": list(roles)},
        params={"clinic_id": str(clinic_id)} if clinic_id else None,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"mode": mode, "roles": list(roles)}


async def login(client, *, email=EMAIL, password=PASSWORD):
    client.cookies.clear()
    return await client.post(f"{AUTH}/login", data={"username": email, "password": password})


def code_at(secret, clock):
    return pyotp.TOTP(secret).at(clock.now(UTC))


async def verify(client, challenge, code, *, path="mfa/verify", headers=None):
    return await client.post(
        f"{AUTH}/{path}",
        json={"mfa_token": challenge["mfa_token"], "code": code},
        headers=headers,
    )


def access(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def assert_challenge(response, mode):
    assert response.status_code == 202, response.text
    assert "dp_access" not in response.cookies and "dp_refresh" not in response.cookies
    assert response.headers["cache-control"] == "no-store"
    challenge = response.json()
    assert challenge["mfa_required"] is True
    assert challenge["mode"] == mode
    assert "access_token" not in challenge and "refresh_token" not in challenge
    return challenge


@pytest.mark.asyncio
async def test_policy_off_preserves_password_login(client, test_clinic, auth_headers):
    res = await login(client)
    assert res.status_code == 200, res.text
    assert "access_token" in res.json()
    res = await client.post(
        f"{AUTH}/mfa/totp/enroll", headers=auth_headers, json={"password": PASSWORD}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_optional_enrollment_mints_session_after_proof_and_stores_hashes(
    client, db_session, auth_headers, test_clinic, key, clock
):
    await policy(client, auth_headers, "optional")
    setup = await client.post(
        f"{AUTH}/mfa/totp/enroll", headers=auth_headers, json={"password": PASSWORD}
    )
    assert setup.status_code == 200, setup.text
    challenge = setup.json()
    assert challenge["qr_code"].startswith("data:image/png;base64,")
    assert setup.headers["cache-control"] == "no-store"
    assert await db_session.scalar(select(func.count()).select_from(UserMfaTotp)) == 0
    assert await db_session.scalar(select(UserMfaChallenge.token_hash)) != challenge["mfa_token"]
    assert (
        await verify(client, challenge, code_at(challenge["secret"], clock))
    ).status_code == 401  # self enrollment requires the active account
    confirmed = await verify(
        client,
        challenge,
        code_at(challenge["secret"], clock),
        path="mfa/totp/confirm",
        headers=auth_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    codes = confirmed.json()["recovery_codes"]
    assert len(set(codes)) == 10
    stored = await db_session.scalar(select(UserMfaTotp.secret_encrypted))
    assert stored != challenge["secret"]
    assert Fernet(key).decrypt(stored.encode()).decode() == challenge["secret"]
    assert not set(codes) & set(await db_session.scalars(select(UserMfaRecoveryCode.code_hash)))
    assert await db_session.scalar(select(func.count()).select_from(UserMfaRecoveryCode)) == 10
    assert await db_session.scalar(select(MfaAuditEntry.event)) == "auth.2fa_enabled"
    assert (await client.get(f"{AUTH}/me", headers=access(confirmed))).status_code == 200
    assert (await client.get(f"{AUTH}/me", headers=auth_headers)).status_code == 401

    response = await login(client)
    login_challenge = assert_challenge(response, "verify")
    assert (
        await client.get(
            f"{AUTH}/me", headers={"Authorization": f"Bearer {login_challenge['mfa_token']}"}
        )
    ).status_code == 401
    # Enrollment consumed this interval. A later interval can authenticate.
    assert (
        await verify(client, login_challenge, code_at(challenge["secret"], clock))
    ).status_code == 401
    clock.now_value += timedelta(seconds=30)
    confirmed = await verify(client, login_challenge, code_at(challenge["secret"], clock))
    assert confirmed.status_code == 200, confirmed.text
    assert (
        await verify(client, login_challenge, code_at(challenge["secret"], clock))
    ).status_code == 401

    login_challenge = assert_challenge(await login(client), "verify")
    confirmed = await verify(client, login_challenge, codes[0])
    assert confirmed.status_code == 200, confirmed.text
    assert await db_session.scalar(select(func.count()).select_from(UserMfaRecoveryCode)) == 9
    reused = await verify(client, assert_challenge(await login(client), "verify"), codes[0])
    assert reused.status_code == 401

    disabled = await client.post(
        f"{AUTH}/mfa/disable",
        headers=access(confirmed),
        json={"password": PASSWORD, "code": codes[1]},
    )
    assert disabled.status_code == 200, disabled.text
    assert await db_session.scalar(select(func.count()).select_from(UserMfaRecoveryCode)) == 0
    assert (await login(client)).status_code == 200


@pytest.mark.asyncio
async def test_mandatory_enrollment_blocks_password_only_sessions(
    client, db_session, auth_headers, test_clinic, key, clock
):
    previous = await login(client)
    assert previous.status_code == 200
    await policy(client, auth_headers, "required_all")
    refreshed = await client.post(
        f"{AUTH}/refresh", json={"refresh_token": previous.json()["refresh_token"]}
    )
    assert refreshed.status_code == 401
    response = await login(client)
    challenge = assert_challenge(response, "enroll")
    assert (await client.get(f"{AUTH}/me")).status_code == 401
    enrolled = await verify(client, challenge, code_at(challenge["secret"], clock))
    assert enrolled.status_code == 200, enrolled.text
    disallowed = await client.post(
        f"{AUTH}/mfa/disable",
        headers=access(enrolled),
        json={"password": PASSWORD, "code": enrolled.json()["recovery_codes"][0]},
    )
    assert disallowed.status_code == 409


@pytest.mark.asyncio
async def test_strictest_clinic_membership_and_role_policy(
    client, db_session, auth_headers, test_clinic, key
):
    user = await db_session.scalar(select(User).where(User.email == EMAIL))
    another = Clinic(name="Second synthetic clinic", tax_id="TEST-MFA")
    db_session.add(another)
    await db_session.flush()
    db_session.add(ClinicMembership(user_id=user.id, clinic_id=another.id, role="dentist"))
    await db_session.commit()
    await policy(client, auth_headers, "required_roles", ["dentist"])
    assert (await login(client)).status_code == 200  # admin is outside the selected role
    another.mfa_policy = {"mode": "required_roles", "roles": ["dentist"]}
    await db_session.commit()
    assert_challenge(await login(client), "enroll")


@pytest.mark.asyncio
async def test_required_invite_returns_enrollment_without_session(
    client, db_session, auth_headers, test_clinic, key
):
    await policy(client, auth_headers, "required_all")
    user = await db_session.scalar(select(User).where(User.email == EMAIL))
    invite, _ = create_invite_token(user.id, user.token_version)
    client.cookies.clear()
    response = await client.post(
        f"{AUTH}/set-password", json={"token": invite, "password": PASSWORD}
    )
    assert_challenge(response, "enroll")
    assert (await client.get(f"{AUTH}/me")).status_code == 401
    used = await client.post(f"{AUTH}/set-password", json={"token": invite, "password": PASSWORD})
    assert used.status_code == 400


@pytest.mark.asyncio
async def test_attempt_limit_survives_a_replaced_challenge(
    client, db_session, auth_headers, test_clinic, key, clock
):
    await policy(client, auth_headers, "required_all")
    for attempt in range(5):
        challenge = assert_challenge(await login(client), "enroll")
        invalid = await verify(client, challenge, "not-a-code")
        assert invalid.status_code == (429 if attempt == 4 else 401), invalid.text
    assert (await login(client)).status_code == 429
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(MfaAuditEntry)
            .where(MfaAuditEntry.event == "auth.2fa_failed")
        )
        == 5
    )
    clock.now_value += timedelta(minutes=15, seconds=1)
    assert_challenge(await login(client), "enroll")


@pytest.mark.asyncio
async def test_expired_challenge_cannot_issue_session(
    client, auth_headers, test_clinic, key, clock
):
    await policy(client, auth_headers, "required_all")
    challenge = assert_challenge(await login(client), "enroll")
    clock.now_value += timedelta(minutes=5, seconds=1)
    assert (await verify(client, challenge, code_at(challenge["secret"], clock))).status_code == 401


@pytest.mark.asyncio
async def test_scoped_admin_reset_forces_reenrollment(
    client, db_session, auth_headers, test_clinic, key, clock
):
    await policy(client, auth_headers, "optional")
    other = Clinic(name="Separate clinic", tax_id="TEST-SEPARATE")
    staff = User(
        email="staff@example.test",
        first_name="Synthetic",
        last_name="Staff",
        password_hash=hash_password(PASSWORD),
    )
    db_session.add_all((other, staff))
    await db_session.flush()
    db_session.add_all(
        (
            ClinicMembership(clinic_id=test_clinic.id, user_id=staff.id, role="dentist"),
            ClinicMembership(clinic_id=other.id, user_id=staff.id, role="dentist"),
        )
    )
    await db_session.commit()
    first_session = await login(client, email=staff.email)
    setup = await client.post(
        f"{AUTH}/mfa/totp/enroll", headers=access(first_session), json={"password": PASSWORD}
    )
    assert setup.status_code == 200, setup.text
    challenge = setup.json()
    enabled = await verify(
        client,
        challenge,
        code_at(challenge["secret"], clock),
        path="mfa/totp/confirm",
        headers=access(first_session),
    )
    assert enabled.status_code == 200, enabled.text
    endpoint = f"{AUTH}/mfa/users/{staff.id}"
    assert (await client.delete(endpoint, headers=access(enabled))).status_code == 403
    assert (await client.delete(endpoint, headers=auth_headers)).status_code == 403
    admin = await db_session.scalar(select(User).where(User.email == EMAIL))
    db_session.add(ClinicMembership(clinic_id=other.id, user_id=admin.id, role="admin"))
    await db_session.commit()
    response = await client.delete(
        endpoint, headers=auth_headers, params={"clinic_id": str(test_clinic.id)}
    )
    assert response.status_code == 204, response.text
    audit = await db_session.scalar(
        select(MfaAuditEntry).where(MfaAuditEntry.event == "auth.2fa_reset")
    )
    assert (audit.user_id, audit.actor_id, audit.clinic_id) == (staff.id, admin.id, test_clinic.id)
    assert (await client.get(f"{AUTH}/me", headers=access(enabled))).status_code == 401
    assert_challenge(await login(client, email=staff.email), "enroll")


@pytest.mark.asyncio
async def test_missing_key_cannot_enable_required_policy(
    client, auth_headers, test_clinic, monkeypatch
):
    monkeypatch.setattr(settings, "MFA_ENCRYPTION_KEY", None)
    response = await client.put(POLICY, headers=auth_headers, json={"mode": "required_all"})
    assert response.status_code == 503
    assert (await login(client)).status_code == 200


def test_independent_encryption_and_rotation(monkeypatch, key):
    encrypted = mfa.cipher().encrypt(b"synthetic-totp")
    monkeypatch.setattr(settings, "SECRET_KEY", "new-staff-jwt-signing-secret-for-tests")
    assert mfa.cipher().decrypt(encrypted) == b"synthetic-totp"
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "MFA_ENCRYPTION_KEY", SecretStr(new_key))
    monkeypatch.setattr(settings, "MFA_PREVIOUS_ENCRYPTION_KEY", SecretStr(key))
    rotated = mfa.cipher().rotate(encrypted)
    monkeypatch.setattr(settings, "MFA_PREVIOUS_ENCRYPTION_KEY", None)
    assert mfa.cipher().decrypt(rotated) == b"synthetic-totp"
