"""Field encryption for the Sistema TS (kit ``IndicazioniTecniche``: the
pincode and the codici fiscali are encrypted "con OpenSSL utilizzando il
certificato SanitelCF" — RSA PKCS#1 v1.5 with the certificate's public key,
base64 output). The certificate ships with the module (``certs/SanitelCF.cer``,
valid to 2027-01-23) and can be replaced per clinic when the portal
regenerates it."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_CERT_PATH = Path(__file__).resolve().parents[1] / "certs" / "SanitelCF.cer"


class CertificateError(ValueError):
    pass


def load_certificate(data: bytes | None = None) -> x509.Certificate:
    """DER or PEM; ``None`` loads the vendored SanitelCF certificate."""
    raw = data if data is not None else _CERT_PATH.read_bytes()
    try:
        if raw.lstrip().startswith(b"-----BEGIN"):
            return x509.load_pem_x509_certificate(raw)
        return x509.load_der_x509_certificate(raw)
    except ValueError as exc:
        raise CertificateError(f"Certificato Sistema TS non valido: {exc}") from exc


@lru_cache(maxsize=8)
def _public_key(cert_bytes: bytes | None) -> rsa.RSAPublicKey:
    key = load_certificate(cert_bytes).public_key()
    if not isinstance(key, rsa.RSAPublicKey):
        raise CertificateError("Il certificato Sistema TS non contiene una chiave RSA")
    return key


def encrypt_field(value: str, cert_bytes: bytes | None = None) -> str:
    """RSA/PKCS1v15 + base64, as ``openssl rsautl -encrypt -certin`` would."""
    key = _public_key(cert_bytes)
    return base64.b64encode(key.encrypt(value.encode("utf-8"), padding.PKCS1v15())).decode("ascii")


def certificate_expiry(cert_bytes: bytes | None = None):
    return load_certificate(cert_bytes).not_valid_after_utc
