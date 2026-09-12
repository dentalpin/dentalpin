"""Authentication service for JWT and password handling."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import bcrypt
from jose import JWTError, jwt

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .models import User


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# Length beats composition rules (#354): 12 is the floor NIST 800-63B
# calls out once composition checks are kept minimal; the letter+number
# check stays because it's what the UI already teaches.
MIN_PASSWORD_LENGTH = 12


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets minimum requirements.

    Returns (is_valid, error_message).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"

    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)

    if not has_letter or not has_number:
        return False, "Password must contain at least one letter and one number"

    return True, ""


def create_access_token(
    user_id: UUID,
    clinic_id: UUID | None = None,
    token_version: int = 0,
    family_id: UUID | None = None,
) -> str:
    """Create a JWT access token.

    ``family_id`` (ADR 0023) names the refresh chain the session belongs
    to, so ``/auth/logout`` can revoke it from the access token alone.
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
        "token_version": token_version,
    }
    if clinic_id:
        payload["clinic_id"] = str(clinic_id)
    if family_id:
        payload["fam"] = str(family_id)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    token_version: int = 0,
    *,
    jti: UUID | None = None,
    family_id: UUID | None = None,
) -> str:
    """Create a JWT refresh token.

    With ``jti``/``family_id`` the token is backed by an
    ``auth_refresh_tokens`` row (ADR 0023) and can be rotated and revoked
    individually; without them it is a legacy stateless token from before
    ADR 0023. :func:`rotate_refresh_token` still accepts those during the
    transition release and migrates them into a tracked family, but nothing
    marks them as used: a legacy token stays replayable until its own
    ``exp`` (``REFRESH_TOKEN_EXPIRE_DAYS``), after which none exist.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "token_version": token_version,
    }
    if jti is not None:
        payload["jti"] = str(jti)
    if family_id is not None:
        payload["fam"] = str(family_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# --- Refresh token rotation (ADR 0023) ---------------------------------------


class RefreshTokenError(Exception):
    """A refresh token that must not be honoured (invalid, revoked, reused)."""


async def issue_refresh_token(
    db: "AsyncSession",
    user: "User",
    *,
    family_id: UUID | None = None,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> tuple[str, UUID]:
    """Persist a refresh-token row and return ``(jwt, family_id)``.

    A new family starts at login / set-password; rotation passes the
    existing ``family_id`` so the chain stays one device's session.
    """
    from .models import RefreshToken

    family_id = family_id or uuid4()
    now = datetime.now(UTC)
    row = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        issued_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent_hash=hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None,
        last_ip=client_ip[:64] if client_ip else None,
    )
    db.add(row)
    await db.flush()
    token = create_refresh_token(
        user.id, token_version=user.token_version, jti=row.id, family_id=family_id
    )
    return token, family_id


async def rotate_refresh_token(
    db: "AsyncSession",
    token: str,
    *,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> tuple["User", str, UUID]:
    """Validate ``token``, revoke it, issue its successor in the same family.

    Returns ``(user, new_refresh_jwt, family_id)``. Raises
    :class:`RefreshTokenError` for anything that must not be honoured.
    Presenting an *already revoked* token is treated as theft: the whole
    family is revoked so neither the thief nor the victim keeps a live
    session (rotation with reuse detection).
    """
    from sqlalchemy import select

    from .models import RefreshToken, User

    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise RefreshTokenError("Invalid or expired refresh token") from exc
    if payload.get("type") != "refresh" or payload.get("sub") is None:
        raise RefreshTokenError("Invalid refresh token")

    user = (
        await db.execute(select(User).where(User.id == UUID(payload["sub"])))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise RefreshTokenError("User not found or inactive")
    if user.token_version != payload.get("token_version", 0):
        raise RefreshTokenError("Token has been revoked")

    jti = payload.get("jti")
    if jti is None:
        # Legacy stateless token from before ADR 0023: accept it and start
        # a tracked family. Not single-use (there is no row to revoke); it
        # dies with its own ``exp``, at most REFRESH_TOKEN_EXPIRE_DAYS after
        # the deploy. Transition-only.
        new_token, family_id = await issue_refresh_token(
            db, user, user_agent=user_agent, client_ip=client_ip
        )
        return user, new_token, family_id

    row = await db.get(RefreshToken, UUID(jti))
    now = datetime.now(UTC)
    if row is None or row.user_id != user.id:
        raise RefreshTokenError("Unknown refresh token")
    if row.revoked_at is not None:
        # Grace window (#421): a duplicate presentation right after rotation
        # (second tab, SSR error re-render) is not theft — hand back the
        # live successor. Older reuse, or reuse of a token whose successor
        # was itself replaced, burns the family.
        grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
        successor = (
            await db.get(RefreshToken, row.replaced_by)
            if row.replaced_by is not None and now - row.revoked_at <= grace
            else None
        )
        if successor is not None and successor.revoked_at is None:
            token = create_refresh_token(
                user.id,
                token_version=user.token_version,
                jti=successor.id,
                family_id=successor.family_id,
            )
            return user, token, successor.family_id
        await revoke_family(db, row.family_id)
        raise RefreshTokenError("Refresh token reuse detected; session revoked")
    if row.expires_at <= now:
        raise RefreshTokenError("Refresh token expired")

    new_token, family_id = await issue_refresh_token(
        db, user, family_id=row.family_id, user_agent=user_agent, client_ip=client_ip
    )
    row.revoked_at = now
    row.replaced_by = UUID(decode_token(new_token)["jti"])
    await db.flush()
    return user, new_token, family_id


async def revoke_family(db: "AsyncSession", family_id: UUID) -> int:
    """Revoke every live token in a family (logout / reuse detection)."""
    from sqlalchemy import update

    from .models import RefreshToken

    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    return result.rowcount or 0


async def revoke_all_for_user(db: "AsyncSession", user_id: UUID) -> int:
    """Sign out every device (admin action / password change hook)."""
    from sqlalchemy import update

    from .models import RefreshToken

    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    return result.rowcount or 0


INVITE_TOKEN_EXPIRE_DAYS = 7


def create_invite_token(user_id: UUID, token_version: int = 0) -> tuple[str, datetime]:
    """One-time "set your password" token handed out as a link.

    Bound to ``token_version`` so consuming it (which bumps the version)
    invalidates the link and every older session at once. Not accepted
    as a bearer token — ``get_current_user`` requires ``type == "access"``.
    """
    expire = datetime.now(UTC) + timedelta(days=INVITE_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "invite",
        "token_version": token_version,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM), expire


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises JWTError if token is invalid or expired.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
