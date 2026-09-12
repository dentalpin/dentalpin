"""HTTP transport to the Sistema TS synchronous service (spec §4.1: HTTPS +
basic authentication with the sender's Sistema TS credentials).

Response (spec §3.3): ``esitoChiamata`` 0 accepted / 1 blocking error /
2 accepted with warnings, ``protocollo`` (17 digits) when 0 or 2, and
``listaMessaggi`` items with ``codice``, ``descrizione``, ``tipo`` (E/W/S).
Parsed by local name so namespace prefixes in the answer do not matter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from lxml import etree

ENDPOINTS = {
    "test": "https://invioSS730pTest.sanita.finanze.it/DocumentoSpesa730pWeb/DocumentoSpesa730pPort",
    "prod": "https://invioSS730p.sanita.finanze.it/DocumentoSpesa730pWeb/DocumentoSpesa730pPort",
}


class TsClientError(RuntimeError):
    """Transport-level failure (retryable)."""


@dataclass
class TsResponse:
    esito: int | None
    protocollo: str | None
    messages: list[dict[str, str]] = field(default_factory=list)
    raw: str = ""

    @property
    def accepted(self) -> bool:
        return self.esito in (0, 2)

    @property
    def blocking_messages(self) -> list[dict[str, str]]:
        return [m for m in self.messages if m.get("tipo") == "E"]


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname


def parse_response(raw: str | bytes) -> TsResponse:
    try:
        root = etree.fromstring(raw.encode("utf-8") if isinstance(raw, str) else raw)
    except etree.XMLSyntaxError as exc:
        raise TsClientError(f"Risposta Sistema TS non valida: {exc}") from exc
    esito: int | None = None
    protocollo: str | None = None
    messages: list[dict[str, str]] = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        name = _local(el)
        text = (el.text or "").strip()
        if name == "esitoChiamata" and text.isdigit():
            esito = int(text)
        elif name == "protocollo" and text:
            protocollo = text
        elif name in ("messaggio", "listaMessaggi") and len(el):
            # listaMessaggi may hold the fields directly or wrap <messaggio> items
            fields = {_local(c): (c.text or "").strip() for c in el if isinstance(c.tag, str)}
            if "codice" in fields:
                messages.append({k: fields.get(k, "") for k in ("codice", "descrizione", "tipo")})
    fault = next(
        (el for el in root.iter() if isinstance(el.tag, str) and _local(el) == "Fault"), None
    )
    if fault is not None and esito is None:
        reason = next(
            (
                c.text
                for c in fault.iter()
                if isinstance(c.tag, str) and _local(c) in ("faultstring", "Text")
            ),
            "",
        )
        raise TsClientError(f"SOAP fault: {reason or 'senza descrizione'}")
    return TsResponse(
        esito=esito,
        protocollo=protocollo,
        messages=messages,
        raw=raw if isinstance(raw, str) else raw.decode("utf-8", "replace"),
    )


def _verify() -> str | bool:
    """CA bundle for the TLS handshake (see ``Settings.SISTEMA_TS_CA_BUNDLE``)."""
    from app import config

    return config.settings.SISTEMA_TS_CA_BUNDLE or True


async def send(
    xml: str, *, environment: str, username: str, password: str, timeout: float = 30.0
) -> TsResponse:
    url = ENDPOINTS.get(environment, ENDPOINTS["test"])
    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'}
    try:
        async with httpx.AsyncClient(
            timeout=timeout, auth=(username, password), verify=_verify()
        ) as client:
            resp = await client.post(url, content=xml.encode("utf-8"), headers=headers)
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            raise TsClientError(
                "TLS: the Sistema TS certificate is not trusted"
                + (
                    " — the test service uses the private Sogei Test CA; "
                    "set SISTEMA_TS_CA_BUNDLE to a PEM bundle that includes it"
                    if environment == "test"
                    else ""
                )
            ) from exc
        raise TsClientError(f"HTTP: {exc}") from exc
    except httpx.HTTPError as exc:
        raise TsClientError(f"HTTP: {exc}") from exc
    if resp.status_code in (401, 403):
        raise TsClientError(f"HTTP {resp.status_code}: credenziali Sistema TS rifiutate")
    if resp.status_code >= 500:
        raise TsClientError(f"HTTP {resp.status_code} dal Sistema TS")
    return parse_response(resp.content)
