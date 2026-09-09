"""VAPID configuration for the WebPush channel.

One keypair per deployment (keys identify the application server to the
push service, not the clinic). Operator generates once::

    python -c "from cryptography.hazmat.primitives.asymmetric import ec;
    from cryptography.hazmat.primitives import serialization;
    k = ec.generate_private_key(ec.SECP256R1());
    print(k.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode())"

and sets ``DENTALPIN_VAPID_PRIVATE_KEY`` (PEM, env only — never committed)
plus ``DENTALPIN_VAPID_SUBJECT`` (a ``mailto:`` contact). The public key
served to browsers for ``PushManager.subscribe`` is derived here from the
private key, so only one secret is ever configured.
"""

from __future__ import annotations

import base64
from functools import lru_cache


def _settings() -> tuple[str, str]:
    """Deployment VAPID pair from app settings (env-backed, Docker-safe).

    ``app.config.Settings`` reads the same ``DENTALPIN_VAPID_*`` env
    vars, so a key in ``.env`` outside Docker is honoured too — unlike
    raw ``os.environ`` reads in a container without env passthrough.
    """
    from app.config import settings

    return (
        (settings.DENTALPIN_VAPID_PRIVATE_KEY or "").strip(),
        (settings.DENTALPIN_VAPID_SUBJECT or "mailto:admin@localhost").strip()
        or "mailto:admin@localhost",
    )


def vapid_configured() -> bool:
    """True when the operator configured a VAPID private key."""
    private_key, _subject = _settings()
    return bool(private_key)


@lru_cache(maxsize=1)
def _parsed_private_key(pem: str):  # noqa: ANN001, ANN202 — cryptography types
    from cryptography.hazmat.primitives import serialization

    return serialization.load_pem_private_key(pem.encode(), password=None)


def vapid_public_key() -> str | None:
    """Derive the base64url public key for ``PushManager.subscribe``.

    Returns None when unconfigured or unparsable (never raises — the
    adapter treats that as unsupported).
    """
    pem, _subject = _settings()
    if not pem:
        return None
    try:
        public_numbers = _parsed_private_key(pem).public_key().public_numbers()
        raw = b"\x04" + public_numbers.x.to_bytes(32, "big") + public_numbers.y.to_bytes(32, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception:
        return None


def vapid_subject() -> str:
    _private_key, subject = _settings()
    return subject


def vapid_private_key() -> str:
    private_key, _subject = _settings()
    return private_key
