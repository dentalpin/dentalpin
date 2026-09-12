import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.modules.sistema_ts.services.crypto import (
    certificate_expiry,
    encrypt_field,
    load_certificate,
)


def test_vendored_certificate_is_the_agenzia_key_and_encrypts_to_128_bytes():
    cert = load_certificate()
    assert "SanitelCF" in cert.subject.rfc4514_string()
    assert certificate_expiry().year >= 2027
    out = encrypt_field("1234567890")
    raw = base64.b64decode(out)
    assert len(raw) == 128  # RSA-1024 as in the kit's samples (172 base64 chars)
    assert encrypt_field("1234567890") != out  # PKCS#1 v1.5 padding is randomised


def test_custom_certificate_roundtrip_with_our_own_key():
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    der = cert.public_bytes(serialization.Encoding.DER)
    for blob in (pem, der):
        token = encrypt_field("RSSMRA80A01H501U", blob)
        plain = key.decrypt(base64.b64decode(token), padding.PKCS1v15())
        assert plain == b"RSSMRA80A01H501U"
