"""QR check-in tokens for appointments.

A signed short-lived JWT (purpose ``checkin``) lets a patient check
themselves in by scanning a QR code — no account, no login. The token
carries only opaque ids; the appointment row stays the authority.
Mirrors the budget public-link posture (signed bearer, TTL, rate
limited) at a smaller scale: single action, 15-minute TTL.

The ``source`` claim (ADR 0037) tells the public page how the token
arrived: ``counter`` (scanned in the clinic, presence proven) auto-
submits; ``reminder`` (mailed link, pre-fetchable) and ``kiosk``
require a deliberate press. A missing or unrecognised source fails
safe to ``reminder`` — never auto-submit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

import qrcode
from fastapi import HTTPException, status
from jose import JWTError, jwt
from qrcode.constants import ERROR_CORRECT_M

from app.config import settings

CHECKIN_TOKEN_TTL_MINUTES = 15

#: Sources the public page branches on (ADR 0037). ``kiosk`` is phase 2
#: (enrolled tablets only); the verifier accepts it but nothing mints it
#: yet, and it never auto-submits.
CHECKIN_SOURCES = ("counter", "reminder", "kiosk")
CheckinSource = Literal["counter", "reminder", "kiosk"]


def _checkin_secret() -> str:
    """Resolve the secret used to sign QR check-in tokens.

    Production deploys must set ``AGENDA_PUBLIC_SECRET_KEY`` — a token
    printed on paper and scanned by strangers must not share a key with
    the session tokens, so a production boot without it refuses to sign
    instead of warning. Falls back to ``SECRET_KEY`` for local/dev
    convenience (budget public-link pattern). A blank or
    whitespace-only value is treated as unset; padding is stripped so
    validation and signing always see the same value.
    """
    key = settings.AGENDA_PUBLIC_SECRET_KEY or ""
    if key.strip():
        return key.strip()
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "AGENDA_PUBLIC_SECRET_KEY is required in production: refusing to "
            "sign QR check-in tokens with the staff-JWT key."
        )
    return settings.SECRET_KEY


class CheckinTokenError(ValueError):
    """Raised when a check-in token is invalid, expired, or mistyped."""


def mint_checkin_token(
    appointment_id: UUID,
    clinic_id: UUID,
    source: CheckinSource = "counter",
    ttl_minutes: int = CHECKIN_TOKEN_TTL_MINUTES,
) -> tuple[str, datetime]:
    """Mint a single-purpose check-in token for an appointment.

    ``source`` records how the token reaches the patient (ADR 0037):
    staff-minted counter QRs auto-submit, mailed reminder links require
    a press. ``ttl_minutes`` lets reminder links live until the end of
    the appointment's clinic-local day instead of fifteen minutes.
    """
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    payload = {
        "type": "checkin",
        "appointment_id": str(appointment_id),
        "clinic_id": str(clinic_id),
        "source": source,
        "exp": expires_at,
    }
    return jwt.encode(payload, _checkin_secret(), algorithm=settings.ALGORITHM), expires_at


def verify_checkin_token(token: str) -> tuple[UUID, UUID, CheckinSource]:
    """Return ``(appointment_id, clinic_id, source)`` or raise CheckinTokenError.

    A missing or unrecognised ``source`` fails safe to ``"reminder"``
    (manual confirm, never auto-submit): legacy tokens predate the
    claim, and a future mint path that drops it must degrade to a tap,
    not a silent auto-submit.
    """
    try:
        payload = jwt.decode(token, _checkin_secret(), algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise CheckinTokenError("Invalid or expired check-in code") from exc
    if payload.get("type") != "checkin":
        raise CheckinTokenError("Invalid or expired check-in code")
    try:
        appointment_id = UUID(payload["appointment_id"])
        clinic_id = UUID(payload["clinic_id"])
    except (KeyError, ValueError, AttributeError) as exc:
        raise CheckinTokenError("Invalid or expired check-in code") from exc
    source = payload.get("source", "reminder")
    if source not in CHECKIN_SOURCES:
        source = "reminder"
    return appointment_id, clinic_id, source


def build_checkin_url(token: str) -> str:
    """Patient-facing check-in URL for a token, origin from config.

    Single home for the origin logic the staff mint endpoint and the
    reminder sweep share, so a copied link and its QR can never point
    at different hosts. 422 when no http(s) origin is configured.
    The first origin must be the patient-facing app: on a deployment
    that lists the API host first, patient links point at the wrong
    host (deterministic, documented here rather than guessed).
    """
    origins = settings.allowed_origins_list
    if not origins:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set ALLOWED_ORIGINS to render check-in QR codes",
        )
    parsed = urlparse(origins[0])
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ALLOWED_ORIGINS must hold http(s) origins",
        )
    return f"{parsed.scheme}://{parsed.netloc}/p/check-in/{token}"


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
