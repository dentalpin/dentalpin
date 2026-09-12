import pytest

from app.modules.sistema_ts.services import ts_client

OK = (
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
    '<ns2:inserimentoDocumentoSpesaResponse xmlns:ns2="http://documentospesap730.sanita.finanze.it">'
    "<esitoChiamata>0</esitoChiamata><protocollo>15120210394302801</protocollo>"
    "</ns2:inserimentoDocumentoSpesaResponse></soapenv:Body></soapenv:Envelope>"
)
WARN = OK.replace(
    "<esitoChiamata>0</esitoChiamata>",
    "<esitoChiamata>2</esitoChiamata><listaMessaggi><messaggio><codice>W01</codice><descrizione>attenzione</descrizione><tipo>W</tipo></messaggio></listaMessaggi>",
)
BAD = (
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
    "<r><esitoChiamata>1</esitoChiamata><listaMessaggi><messaggio><codice>E01</codice><descrizione>Codice fiscale non valido</descrizione><tipo>E</tipo></messaggio>"
    "<messaggio><codice>S99</codice><descrizione>stat</descrizione><tipo>S</tipo></messaggio></listaMessaggi></r></soapenv:Body></soapenv:Envelope>"
)
FAULT = (
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
    "<soapenv:Fault><faultcode>Server</faultcode><faultstring>pincode errato</faultstring></soapenv:Fault></soapenv:Body></soapenv:Envelope>"
)


def test_parse_accepted_and_warnings():
    r = ts_client.parse_response(OK)
    assert r.esito == 0 and r.protocollo == "15120210394302801" and r.accepted and r.messages == []
    w = ts_client.parse_response(WARN)
    assert (
        w.esito == 2
        and w.accepted
        and w.messages[0]["codice"] == "W01"
        and w.blocking_messages == []
    )


def test_parse_rejection_and_fault():
    b = ts_client.parse_response(BAD)
    assert b.esito == 1 and not b.accepted and [m["codice"] for m in b.blocking_messages] == ["E01"]
    with pytest.raises(ts_client.TsClientError, match="pincode errato"):
        ts_client.parse_response(FAULT)
    with pytest.raises(ts_client.TsClientError):
        ts_client.parse_response("<not xml")


class _Resp:
    def __init__(self, status, content):
        self.status_code, self.content = status, content


class _Client:
    last = {}

    def __init__(self, **kw):
        _Client.last["init"] = kw

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, content=None, headers=None):
        _Client.last.update(url=url, content=content, headers=headers)
        return _Resp(_Client.status, _Client.body)


@pytest.mark.asyncio
async def test_send_uses_basic_auth_and_the_environment_endpoint(monkeypatch):
    monkeypatch.setattr(ts_client.httpx, "AsyncClient", _Client)
    _Client.status, _Client.body = 200, OK.encode()
    r = await ts_client.send("<x/>", environment="prod", username="PROVAX00X00X000Y", password="pw")
    assert r.protocollo and _Client.last["url"].startswith("https://invioSS730p.sanita.finanze.it/")
    assert _Client.last["init"]["auth"] == ("PROVAX00X00X000Y", "pw")
    assert _Client.last["headers"]["Content-Type"].startswith("text/xml")
    _Client.status, _Client.body = 401, b""
    with pytest.raises(ts_client.TsClientError, match="credenziali"):
        await ts_client.send("<x/>", environment="test", username="u", password="p")


@pytest.mark.asyncio
async def test_send_passes_the_configured_ca_bundle(monkeypatch):
    from app import config

    monkeypatch.setattr(ts_client.httpx, "AsyncClient", _Client)
    _Client.status, _Client.body = 200, OK.encode()
    monkeypatch.setattr(config.settings, "SISTEMA_TS_CA_BUNDLE", "/etc/ssl/sogei-test.pem")
    await ts_client.send("<x/>", environment="test", username="u", password="p")
    assert _Client.last["init"]["verify"] == "/etc/ssl/sogei-test.pem"
    monkeypatch.setattr(config.settings, "SISTEMA_TS_CA_BUNDLE", "")
    await ts_client.send("<x/>", environment="test", username="u", password="p")
    assert _Client.last["init"]["verify"] is True


@pytest.mark.asyncio
async def test_send_explains_an_untrusted_test_certificate(monkeypatch):
    class _Boom(_Client):
        async def post(self, url, content=None, headers=None):
            raise ts_client.httpx.ConnectError(
                "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
            )

    monkeypatch.setattr(ts_client.httpx, "AsyncClient", _Boom)
    with pytest.raises(ts_client.TsClientError, match="SISTEMA_TS_CA_BUNDLE"):
        await ts_client.send("<x/>", environment="test", username="u", password="p")
