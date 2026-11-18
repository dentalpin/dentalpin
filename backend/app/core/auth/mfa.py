"""Staff MFA policy, encrypted credentials and single-use challenges."""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Literal, Never
from uuid import UUID

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.events import EventType, event_bus

from .models import (
    Clinic,
    ClinicMembership,
    MfaAuditEntry,
    User,
    UserMfaChallenge,
    UserMfaRecoveryCode,
    UserMfaTotp,
)
from .service import revoke_all_for_user

CHALLENGE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
LOCKOUT = timedelta(minutes=15)
ChallengePurpose = Literal["verify", "required", "self"]
PolicyMode = Literal["off", "optional", "required_all", "required_roles"]


class MfaPolicy(BaseModel):
    mode: PolicyMode = "off"
    roles: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_roles(self) -> "MfaPolicy":
        if (self.mode == "required_roles") != bool(self.roles):
            raise ValueError("Select at least one role for role-based enforcement")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("Roles must be unique")
        return self


class MfaChallengeResponse(BaseModel):
    mfa_required: Literal[True] = True
    mfa_token: str
    mode: Literal["verify", "enroll"]
    secret: str | None = None
    qr_code: str | None = None


class MfaProof(BaseModel):
    mfa_token: str = Field(min_length=43, max_length=43)
    code: str = Field(min_length=1, max_length=64)


class MfaPassword(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class MfaDisable(MfaPassword):
    code: str = Field(min_length=1, max_length=64)


class MfaStatus(BaseModel):
    enabled: bool
    allowed: bool
    required: bool


def cipher() -> MultiFernet:
    keys = [settings.MFA_ENCRYPTION_KEY, settings.MFA_PREVIOUS_ENCRYPTION_KEY]
    if keys[0] is None or not keys[0].get_secret_value():
        raise HTTPException(503, "mfa_unavailable")
    try:
        values = [key.get_secret_value() for key in keys if key and key.get_secret_value()]
        if settings.SECRET_KEY in values:
            raise ValueError("MFA key must be independent")
        return MultiFernet([Fernet(value) for value in values])
    except ValueError as exc:
        raise HTTPException(503, "mfa_unavailable") from exc


def _decrypt(secret_encrypted: str) -> str:
    try:
        return cipher().decrypt(secret_encrypted.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(503, "mfa_unavailable") from exc


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def membership_policies(db: AsyncSession, user_id: UUID) -> list[tuple[MfaPolicy, str]]:
    rows = await db.execute(
        select(Clinic.mfa_policy, ClinicMembership.role)
        .join(ClinicMembership, Clinic.id == ClinicMembership.clinic_id)
        .where(ClinicMembership.user_id == user_id)
    )
    return [(MfaPolicy.model_validate(policy), role) for policy, role in rows]


async def mfa_status(db: AsyncSession, user: User) -> MfaStatus:
    policies = await membership_policies(db, user.id)
    required = user.mfa_reenroll_required or any(
        policy.mode == "required_all" or policy.mode == "required_roles" and role in policy.roles
        for policy, role in policies
    )
    return MfaStatus(
        enabled=await db.get(UserMfaTotp, user.id) is not None,
        allowed=required or any(policy.mode != "off" for policy, _ in policies),
        required=required,
    )


async def lock_user(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.memberships))
        .with_for_update(of=User)
        .execution_options(populate_existing=True)
    )


def check_lockout(user: User) -> None:
    if user.mfa_locked_until is None:
        return
    now = datetime.now(UTC)
    if user.mfa_locked_until > now:
        retry = max(1, int((user.mfa_locked_until - now).total_seconds()))
        raise HTTPException(429, "mfa_locked", headers={"Retry-After": str(retry)})
    _clear_attempts(user)


def _clear_attempts(user: User) -> None:
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None


async def new_challenge(
    db: AsyncSession, user: User, purpose: ChallengePurpose
) -> MfaChallengeResponse:
    """Requires the user's row lock until the challenge is committed."""
    check_lockout(user)
    keyring = cipher()
    token = secrets.token_urlsafe(32)
    challenge = await db.get(UserMfaChallenge, user.id)
    if challenge is None:
        challenge = UserMfaChallenge(user_id=user.id)
        db.add(challenge)
    challenge.token_hash = _digest(token)
    challenge.token_version = user.token_version
    challenge.expires_at = datetime.now(UTC) + CHALLENGE_TTL
    challenge.purpose = purpose
    challenge.secret_encrypted = None

    if purpose == "verify":
        return MfaChallengeResponse(mfa_token=token, mode="verify")

    secret = pyotp.random_base32()
    challenge.secret_encrypted = keyring.encrypt(secret.encode()).decode()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="DentalPin")
    encoded = BytesIO()
    qrcode.make(uri).save(encoded, format="PNG")
    return MfaChallengeResponse(
        mfa_token=token,
        mode="enroll",
        secret=secret,
        qr_code="data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode(),
    )


async def locked_challenge(
    db: AsyncSession,
    token: str,
    purposes: tuple[ChallengePurpose, ...],
    *,
    expected_user: User | None = None,
) -> tuple[User, UserMfaChallenge]:
    invalid = HTTPException(401, "mfa_expired")
    digest = _digest(token)
    user_id = await db.scalar(
        select(UserMfaChallenge.user_id).where(UserMfaChallenge.token_hash == digest)
    )
    if user_id is None or expected_user is not None and user_id != expected_user.id:
        raise invalid
    expected_version = expected_user.token_version if expected_user is not None else None
    user = await lock_user(db, user_id)
    challenge = await db.get(UserMfaChallenge, user_id, populate_existing=True)
    if (
        user is None
        or not user.is_active
        or challenge is None
        or challenge.token_hash != digest
        or challenge.purpose not in purposes
        or challenge.expires_at <= datetime.now(UTC)
        or challenge.token_version != user.token_version
        or expected_version is not None
        and user.token_version != expected_version
    ):
        raise invalid
    check_lockout(user)
    return user, challenge


def _matching_counter(secret: str, code: str, *, last_counter: int | None = None) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    now = datetime.now(UTC)
    for offset in (0, -1, 1):
        candidate = now + timedelta(seconds=offset * totp.interval)
        counter = totp.timecode(candidate)
        if (last_counter is None or counter > last_counter) and totp.verify(
            code, for_time=candidate
        ):
            return counter
    return None


async def audit(
    db: AsyncSession,
    event: str,
    user_id: UUID,
    actor_id: UUID,
    clinic_id: UUID | None = None,
) -> None:
    now = datetime.now(UTC)
    db.add(
        MfaAuditEntry(
            event=event, user_id=user_id, actor_id=actor_id, clinic_id=clinic_id, created_at=now
        )
    )
    # The explicit names here are what the event catalog and consumers track.
    payload = {
        "user_id": str(user_id),
        "actor_id": str(actor_id),
        "clinic_id": str(clinic_id) if clinic_id is not None else None,
        "occurred_at": now.isoformat(),
    }
    if event == EventType.AUTH_2FA_ENABLED:
        await event_bus.publish(EventType.AUTH_2FA_ENABLED, payload, db=db)
    elif event == EventType.AUTH_2FA_DISABLED:
        await event_bus.publish(EventType.AUTH_2FA_DISABLED, payload, db=db)
    elif event == EventType.AUTH_2FA_RESET:
        await event_bus.publish(EventType.AUTH_2FA_RESET, payload, db=db)
    else:
        await event_bus.publish(EventType.AUTH_2FA_FAILED, payload, db=db)


async def _fail_code(db: AsyncSession, user: User) -> Never:
    user.mfa_failed_attempts += 1
    if user.mfa_failed_attempts >= MAX_ATTEMPTS:
        user.mfa_locked_until = datetime.now(UTC) + LOCKOUT
        await db.execute(delete(UserMfaChallenge).where(UserMfaChallenge.user_id == user.id))
    await audit(db, EventType.AUTH_2FA_FAILED, user.id, user.id)
    await db.commit()
    check_lockout(user)
    raise HTTPException(401, "mfa_invalid_code")


async def verify_code(db: AsyncSession, user: User, credential: UserMfaTotp, code: str) -> None:
    """Consume a factor under the user lock, checking replay across workers."""
    check_lockout(user)
    code = code.strip()
    secret = _decrypt(credential.secret_encrypted)
    counter = _matching_counter(secret, code, last_counter=credential.last_counter)
    if counter is not None:
        credential.last_counter = counter
    else:
        recovery_code = await db.get(UserMfaRecoveryCode, (user.id, _digest(code)))
        if recovery_code is None:
            await _fail_code(db, user)
        else:
            await db.delete(recovery_code)
    _clear_attempts(user)


async def enroll(db: AsyncSession, user: User, challenge: UserMfaChallenge, code: str) -> list[str]:
    if challenge.secret_encrypted is None or await db.get(UserMfaTotp, user.id):
        raise HTTPException(409, "mfa_already_enabled")
    secret = _decrypt(challenge.secret_encrypted)
    counter = _matching_counter(secret, code.strip())
    if counter is None:
        await _fail_code(db, user)
    await db.delete(challenge)
    db.add(
        UserMfaTotp(
            user_id=user.id,
            secret_encrypted=cipher().encrypt(secret.encode()).decode(),
            last_counter=counter,
            confirmed_at=datetime.now(UTC),
        )
    )
    recovery_codes = [secrets.token_urlsafe(12) for _ in range(10)]
    db.add_all(
        UserMfaRecoveryCode(user_id=user.id, code_hash=_digest(code)) for code in recovery_codes
    )
    _clear_attempts(user)
    user.mfa_reenroll_required = False
    await _revoke_sessions(db, user)
    await audit(db, EventType.AUTH_2FA_ENABLED, user.id, user.id)
    return recovery_codes


async def _revoke_sessions(db: AsyncSession, user: User) -> None:
    user.token_version += 1
    await revoke_all_for_user(db, user.id)


async def clear_enrollment(
    db: AsyncSession, user: User, *, actor_id: UUID, reset_clinic: UUID | None = None
) -> None:
    for model in (UserMfaTotp, UserMfaRecoveryCode, UserMfaChallenge):
        await db.execute(delete(model).where(model.user_id == user.id))
    _clear_attempts(user)
    user.mfa_reenroll_required = reset_clinic is not None
    await _revoke_sessions(db, user)
    event = EventType.AUTH_2FA_RESET if reset_clinic is not None else EventType.AUTH_2FA_DISABLED
    await audit(db, event, user.id, actor_id, reset_clinic)
