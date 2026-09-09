"""NAV Online Számla 3.0 HTTP client: tokenExchange, manageInvoice,
queryTransactionStatus.

One ``httpx.AsyncClient`` per call with a timeout, transport errors
mapped to :class:`NavClientError` — the verifactu ``aeat_client`` shape.
Envelopes are rendered by hand (the API XML is small and fixed);
responses parsed with lxml. Everything network-facing is in this file
so the queue tests monkeypatch ``post_xml`` only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from xml.sax.saxutils import escape

import httpx
from lxml import etree

from . import crypto

NS_API = "http://schemas.nav.gov.hu/OSA/3.0/api"
NS_COMMON = "http://schemas.nav.gov.hu/NTCA/1.0/common"
_NSMAP = {"api": NS_API, "common": NS_COMMON}

ENDPOINTS = {
    "test": "https://api-test.onlineszamla.nav.gov.hu/invoiceService/v3",
    "prod": "https://api.onlineszamla.nav.gov.hu/invoiceService/v3",
}
_TIMEOUT = 30.0

SOFTWARE_NAME = "DentalPin"
SOFTWARE_VERSION = "2.0.0"


class NavClientError(Exception):
    """Transport-level failure (no parseable NAV response)."""


@dataclass
class Credentials:
    login: str
    password: str
    signature_key: str
    exchange_key: str
    tax_number: str  # 8-digit törzsszám
    software_id: str
    software_dev_contact: str | None = None


@dataclass
class NavResponse:
    func_code: str  # OK | ERROR
    error_code: str | None = None
    message: str | None = None
    transaction_id: str | None = None
    exchange_token: str | None = None
    processing: list[ProcessingResult] = field(default_factory=list)
    raw: str = ""

    @property
    def ok(self) -> bool:
        return self.func_code == "OK"


@dataclass
class ProcessingResult:
    index: int
    invoice_status: str  # RECEIVED | PROCESSING | SAVED | DONE | ABORTED
    error_code: str | None = None
    message: str | None = None


def endpoint_for(environment: str) -> str:
    return ENDPOINTS["prod" if environment == "prod" else "test"]


# ------------------------------------------------------------------ envelopes
def _header_user_software(
    creds: Credentials, request_id: str, now: datetime, signature: str
) -> str:
    _, iso = crypto.timestamp_utc(now)
    return (
        "<common:header>"
        f"<common:requestId>{request_id}</common:requestId>"
        f"<common:timestamp>{iso}</common:timestamp>"
        "<common:requestVersion>3.0</common:requestVersion>"
        "<common:headerVersion>1.0</common:headerVersion>"
        "</common:header>"
        "<common:user>"
        f"<common:login>{escape(creds.login)}</common:login>"
        f'<common:passwordHash cryptoType="SHA-512">{crypto.password_hash(creds.password)}</common:passwordHash>'
        f"<common:taxNumber>{creds.tax_number}</common:taxNumber>"
        f'<common:requestSignature cryptoType="SHA3-512">{signature}</common:requestSignature>'
        "</common:user>"
        "<software>"
        f"<softwareId>{creds.software_id}</softwareId>"
        f"<softwareName>{SOFTWARE_NAME}</softwareName>"
        "<softwareOperation>LOCAL_SOFTWARE</softwareOperation>"
        f"<softwareMainVersion>{SOFTWARE_VERSION}</softwareMainVersion>"
        f"<softwareDevName>{SOFTWARE_NAME}</softwareDevName>"
        f"<softwareDevContact>{escape(creds.software_dev_contact or 'support@dentalpin.com')}</softwareDevContact>"
        "<softwareDevCountryCode>HU</softwareDevCountryCode>"
        "</software>"
    )


def token_exchange_request(creds: Credentials, *, request_id: str | None = None, now=None) -> str:
    request_id = request_id or crypto.new_request_id()
    now, _ = crypto.timestamp_utc(now)
    signature = crypto.request_signature(request_id, now, creds.signature_key)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<TokenExchangeRequest xmlns="{NS_API}" xmlns:common="{NS_COMMON}">'
        f"{_header_user_software(creds, request_id, now, signature)}"
        "</TokenExchangeRequest>"
    )


def manage_invoice_request(
    creds: Credentials,
    exchange_token: str,
    operations: list[tuple[str, str]],
    *,
    request_id: str | None = None,
    now=None,
) -> str:
    """``operations``: ``[(operation, invoice_xml), …]`` in index order."""
    request_id = request_id or crypto.new_request_id()
    now, _ = crypto.timestamp_utc(now)
    encoded = [(op, crypto.encode_invoice(xml)) for op, xml in operations]
    signature = crypto.request_signature(
        request_id,
        now,
        creds.signature_key,
        [crypto.operation_hash(op, b64) for op, b64 in encoded],
    )
    ops_xml = "".join(
        "<invoiceOperation>"
        f"<index>{i}</index><invoiceOperation>{op}</invoiceOperation>"
        f"<invoiceData>{b64}</invoiceData>"
        "</invoiceOperation>"
        for i, (op, b64) in enumerate(encoded, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<ManageInvoiceRequest xmlns="{NS_API}" xmlns:common="{NS_COMMON}">'
        f"{_header_user_software(creds, request_id, now, signature)}"
        f"<exchangeToken>{exchange_token}</exchangeToken>"
        f"<invoiceOperations><compressedContent>false</compressedContent>{ops_xml}</invoiceOperations>"
        "</ManageInvoiceRequest>"
    )


def query_status_request(
    creds: Credentials, transaction_id: str, *, request_id: str | None = None, now=None
) -> str:
    request_id = request_id or crypto.new_request_id()
    now, _ = crypto.timestamp_utc(now)
    signature = crypto.request_signature(request_id, now, creds.signature_key)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<QueryTransactionStatusRequest xmlns="{NS_API}" xmlns:common="{NS_COMMON}">'
        f"{_header_user_software(creds, request_id, now, signature)}"
        f"<transactionId>{transaction_id}</transactionId>"
        "</QueryTransactionStatusRequest>"
    )


# ------------------------------------------------------------------ transport
async def post_xml(environment: str, operation: str, body: str) -> str:
    """POST an envelope to ``/<operation>``; returns the raw response body.

    NAV answers business errors with HTTP 4xx *and* an XML body, so any
    parseable body is returned for :func:`parse_response`; only transport
    failures raise.
    """
    url = f"{endpoint_for(environment)}/{operation}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(
                url, content=body.encode("utf-8"), headers={"Content-Type": "application/xml"}
            )
    except httpx.HTTPError as exc:
        raise NavClientError(str(exc)) from exc
    if not res.text:
        raise NavClientError(f"empty response (HTTP {res.status_code})")
    return res.text


# ------------------------------------------------------------------ parsing
def _text(node, xpath: str) -> str | None:
    found = node.xpath(xpath, namespaces=_NSMAP)
    if not found:
        return None
    value = found[0] if isinstance(found[0], str) else (found[0].text or "")
    return value.strip() or None


def parse_response(xml_text: str) -> NavResponse:
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise NavClientError(f"unparseable NAV response: {exc}") from exc

    func_code = _text(root, ".//common:result/common:funcCode") or "ERROR"
    resp = NavResponse(
        func_code=func_code,
        error_code=_text(root, ".//common:result/common:errorCode"),
        message=_text(root, ".//common:result/common:message"),
        transaction_id=_text(root, ".//api:transactionId"),
        exchange_token=_text(root, ".//api:encodedExchangeToken"),
        raw=xml_text,
    )
    for pr in root.xpath(".//api:processingResults/api:processingResult", namespaces=_NSMAP):
        # Prefer the first ERROR-level business/technical validation message.
        err_code = None
        err_msg = None
        for vm in pr.xpath(
            "api:technicalValidationMessages | api:businessValidationMessages", namespaces=_NSMAP
        ):
            if (_text(vm, "api:validationResultCode") or "").upper() == "ERROR":
                err_code = _text(vm, "api:validationErrorCode") or err_code
                err_msg = _text(vm, "api:message") or err_msg
                break
        resp.processing.append(
            ProcessingResult(
                index=int(_text(pr, "api:index") or "0"),
                invoice_status=(_text(pr, "api:invoiceStatus") or "").upper(),
                error_code=err_code,
                message=err_msg,
            )
        )
    return resp


# ------------------------------------------------------------------ high level
async def exchange_token(creds: Credentials, environment: str) -> str:
    raw = await post_xml(environment, "tokenExchange", token_exchange_request(creds))
    resp = parse_response(raw)
    if not resp.ok or not resp.exchange_token:
        raise NavClientError(f"tokenExchange failed: {resp.error_code} {resp.message}")
    return crypto.decrypt_exchange_token(resp.exchange_token, creds.exchange_key)


async def manage_invoice(
    creds: Credentials, environment: str, token: str, operations: list[tuple[str, str]]
) -> NavResponse:
    raw = await post_xml(
        environment, "manageInvoice", manage_invoice_request(creds, token, operations)
    )
    return parse_response(raw)


async def query_transaction_status(
    creds: Credentials, environment: str, transaction_id: str
) -> NavResponse:
    raw = await post_xml(
        environment, "queryTransactionStatus", query_status_request(creds, transaction_id)
    )
    return parse_response(raw)
