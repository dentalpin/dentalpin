"""QR check-in tokens for appointments.

A signed short-lived JWT (purpose ``checkin``) lets a patient check
themselves in by scanning a QR code — no account, no login. The token
carries only opaque ids; the appointment row stays the authority.
Mirrors the budget public-link posture (signed bearer, TTL, rate
limited) at a smaller scale: single action, 15-minute TTL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import qrcode
from jose import JWTError, jwt
from qrcode.constants import ERROR_CORRECT_M

from app.config import settings

CHECKIN_TOKEN_TTL_MINUTES = 15

warned_no_dedicated_secret = False


def _checkin_secret() -> str:
    """Resolve the secret used to sign QR check-in tokens.

    Production deploys must set ``AGENDA_PUBLIC_SECRET_KEY`` — a token
    printed on paper and scanned by strangers must not share a key with
    the session tokens. Falls back to ``SECRET_KEY`` for local/dev
    convenience (budget public-link pattern).
    """
    global warned_no_dedicated_secret
    if settings.AGENDA_PUBLIC_SECRET_KEY:
        return settings.AGENDA_PUBLIC_SECRET_KEY
    if settings.ENVIRONMENT == "production" and not warned_no_dedicated_secret:
        import logging

        logging.getLogger(__name__).warning(
            "AGENDA_PUBLIC_SECRET_KEY is unset in production — QR check-in "
            "tokens share SECRET_KEY with session tokens. Set it explicitly."
        )
        warned_no_dedicated_secret = True
    return settings.SECRET_KEY


class CheckinTokenError(ValueError):
    """Raised when a check-in token is invalid, expired, or mistyped."""


def mint_checkin_token(appointment_id: UUID, clinic_id: UUID) -> tuple[str, datetime]:
    """Mint a single-purpose check-in token for an appointment."""
    expires_at = datetime.now(UTC) + timedelta(minutes=CHECKIN_TOKEN_TTL_MINUTES)
    payload = {
        "type": "checkin",
        "appointment_id": str(appointment_id),
        "clinic_id": str(clinic_id),
        "exp": expires_at,
    }
    return jwt.encode(payload, _checkin_secret(), algorithm=settings.ALGORITHM), expires_at


def verify_checkin_token(token: str) -> tuple[UUID, UUID]:
    """Return ``(appointment_id, clinic_id)`` or raise CheckinTokenError."""
    try:
        payload = jwt.decode(token, _checkin_secret(), algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise CheckinTokenError("Invalid or expired check-in code") from exc
    if payload.get("type") != "checkin":
        raise CheckinTokenError("Invalid or expired check-in code")
    try:
        return UUID(payload["appointment_id"]), UUID(payload["clinic_id"])
    except (KeyError, ValueError, AttributeError) as exc:
        raise CheckinTokenError("Invalid or expired check-in code") from exc


def render_checkin_qr(url: str) -> bytes:
    """Render the check-in URL as PNG bytes (ECC level M)."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
