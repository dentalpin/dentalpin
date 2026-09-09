"""NAV Online Számla 3.0 request-security primitives.

Per the NAV interface specification (v3.0):

* ``passwordHash``  — SHA-512 of the technical user's password, upper hex.
* ``requestSignature`` — SHA3-512 of ``requestId + timestamp(yyyyMMddHHmmss, UTC)
  + signatureKey`` for signature-only requests (tokenExchange, queries);
  ``manageInvoice`` appends, per operation, ``SHA3-512(operationType +
  base64(invoiceData))`` upper hex, in index order, before hashing.
* ``exchangeToken`` — the response carries ``encodedExchangeToken``:
  base64 of AES-128-ECB(PKCS5) ciphertext; decrypt with the 16-byte
  exchange key.

Pure functions, no I/O — the tests pin them against self-consistent
vectors and the ECB roundtrip.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import string
from datetime import UTC, datetime

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_ALNUM = string.ascii_uppercase + string.digits


def new_request_id() -> str:
    """``requestId``: 1–30 chars ``[0-9A-Za-z]``; unique per request."""
    return "DP" + "".join(secrets.choice(_ALNUM) for _ in range(24))


def timestamp_utc(now: datetime | None = None) -> tuple[datetime, str]:
    """The header ``timestamp`` (ISO, UTC, millisecond precision) and its
    ``yyyyMMddHHmmss`` form used inside the signature."""
    now = now or datetime.now(UTC)
    now = now.astimezone(UTC)
    iso = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    return now, iso


def signature_timestamp(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def password_hash(password: str) -> str:
    return hashlib.sha512(password.encode("utf-8")).hexdigest().upper()


def operation_hash(operation: str, invoice_b64: str) -> str:
    return hashlib.sha3_512((operation + invoice_b64).encode("utf-8")).hexdigest().upper()


def request_signature(
    request_id: str,
    now: datetime,
    signature_key: str,
    operation_hashes: list[str] | None = None,
) -> str:
    base = request_id + signature_timestamp(now) + signature_key + "".join(operation_hashes or [])
    return hashlib.sha3_512(base.encode("utf-8")).hexdigest().upper()


def encode_invoice(xml_text: str) -> str:
    return base64.b64encode(xml_text.encode("utf-8")).decode("ascii")


def decrypt_exchange_token(encoded_token: str, exchange_key: str) -> str:
    """AES-128-ECB (PKCS5) decrypt of the base64 ``encodedExchangeToken``."""
    key = exchange_key.encode("utf-8")
    if len(key) != 16:
        raise ValueError("NAV exchange key must be exactly 16 characters")
    data = base64.b64decode(encoded_token)
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()  # noqa: S305 — NAV mandates ECB
    padded = decryptor.update(data) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return plain.decode("utf-8")


def encrypt_exchange_token(token: str, exchange_key: str) -> str:
    """Inverse of :func:`decrypt_exchange_token` — only tests/sandbox fakes need it."""
    key = exchange_key.encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(token.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()  # noqa: S305
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode("ascii")
