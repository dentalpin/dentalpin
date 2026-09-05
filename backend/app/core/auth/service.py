"""Authentication service for JWT and password handling."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
from jose import jwt

from app.config import settings


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
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
        "token_version": token_version,
    }
    if clinic_id:
        payload["clinic_id"] = str(clinic_id)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: UUID, token_version: int = 0) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "token_version": token_version,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


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
