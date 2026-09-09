"""NAV request-security primitives (self-consistent vectors + ECB roundtrip)."""

import hashlib
from datetime import UTC, datetime

from app.modules.nav_online.services import crypto


def test_password_hash_is_upper_sha512():
    assert crypto.password_hash("secret") == hashlib.sha512(b"secret").hexdigest().upper()


def test_request_signature_composition():
    now = datetime(2026, 9, 6, 12, 34, 56, tzinfo=UTC)
    sig = crypto.request_signature("REQ1", now, "KEY")
    assert sig == hashlib.sha3_512(b"REQ120260906123456KEY").hexdigest().upper()
    op = crypto.operation_hash("CREATE", "QUJD")
    assert op == hashlib.sha3_512(b"CREATEQUJD").hexdigest().upper()
    sig2 = crypto.request_signature("REQ1", now, "KEY", [op])
    assert sig2 == hashlib.sha3_512(("REQ120260906123456KEY" + op).encode()).hexdigest().upper()


def test_exchange_token_aes_ecb_roundtrip():
    key = "0123456789abcdef"
    encoded = crypto.encrypt_exchange_token("TOKEN-123", key)
    assert crypto.decrypt_exchange_token(encoded, key) == "TOKEN-123"


def test_request_id_and_timestamp_shapes():
    rid = crypto.new_request_id()
    assert 1 <= len(rid) <= 30 and rid.isalnum()
    now, iso = crypto.timestamp_utc(datetime(2026, 9, 6, 1, 2, 3, 456000, tzinfo=UTC))
    assert iso == "2026-09-06T01:02:03.456Z"
    assert crypto.signature_timestamp(now) == "20260906010203"
