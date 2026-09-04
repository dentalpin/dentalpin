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
import os


def vapid_configured() -> bool:
    """True when the operator configured a VAPID private key."""
    return bool(os.environ.get("DENTALPIN_VAPID_PRIVATE_KEY", "").strip())


def vapid_public_key() -> str | None:
    """Derive the base64url public key for ``PushManager.subscribe``.

    Returns None when unconfigured or unparsable (never raises — the
    adapter treats that as unsupported).
    """
    pem = os.environ.get("DENTALPIN_VAPID_PRIVATE_KEY", "").strip()
    if not pem:
        return None
    try:
        from cryptography.hazmat.primitives import serialization

        private_key = serialization.load_pem_private_key(pem.encode(), password=None)
        public_numbers = private_key.public_key().public_numbers()
        raw = b"\x04" + public_numbers.x.to_bytes(32, "big") + public_numbers.y.to_bytes(32, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception:
        return None


def vapid_subject() -> str:
    return os.environ.get("DENTALPIN_VAPID_SUBJECT", "mailto:admin@localhost")


def vapid_private_key() -> str:
    return os.environ.get("DENTALPIN_VAPID_PRIVATE_KEY", "").strip()
