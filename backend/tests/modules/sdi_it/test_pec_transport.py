"""PEC transport with fake smtplib/imaplib: message shape, receipt extraction, SDI reply address."""

import email
from email.message import EmailMessage

import pytest

from app.modules.sdi_it.services import pec_transport as pt

CREDS = pt.PecCredentials(
    address="studio@pec.example.it",
    smtp_host="smtps.example.it",
    smtp_port=465,
    imap_host="imaps.example.it",
    imap_port=993,
    username="studio@pec.example.it",
    password="pw",
)
NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/messaggi/v1.0"


def _rc(file_name="IT01234567897_00001.xml") -> str:
    return (
        f'<ns3:RicevutaConsegna xmlns:ns3="{NS}"><IdentificativoSdI>77</IdentificativoSdI>'
        f"<NomeFile>{file_name}</NomeFile></ns3:RicevutaConsegna>"
    )


def _sdi_message(sender: str, attachments: list[tuple[str, bytes]]) -> bytes:
    msg = EmailMessage()
    msg["From"] = f"Sistema di Interscambio <{sender}>"
    msg["To"] = CREDS.address
    msg["Subject"] = "RICEZIONE"
    msg.set_content("ricevuta")
    for name, payload in attachments:
        sub = "zip" if name.endswith(".zip") else "xml"
        msg.add_attachment(payload, maintype="application", subtype=sub, filename=name)
    return msg.as_bytes()


class _FakeSMTP:
    sent: list[EmailMessage] = []
    logins: list[tuple[str, str]] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, u, p):
        _FakeSMTP.logins.append((u, p))

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)

    def starttls(self, context=None):
        pass


@pytest.mark.asyncio
async def test_send_file_attaches_the_xml_and_addresses_the_sdi(monkeypatch):
    _FakeSMTP.sent.clear()
    monkeypatch.setattr(pt.smtplib, "SMTP_SSL", _FakeSMTP)
    mid = await pt.send_file(CREDS, "sdi01@pec.fatturapa.it", "IT01234567897_00001.xml", "<x/>")
    assert mid.startswith("<") and _FakeSMTP.logins[-1] == (CREDS.username, "pw")
    msg = _FakeSMTP.sent[-1]
    assert msg["To"] == "sdi01@pec.fatturapa.it" and msg["From"] == CREDS.address
    att = [p for p in msg.walk() if p.get_filename()]
    assert att[0].get_filename() == "IT01234567897_00001.xml"
    assert att[0].get_payload(decode=True) == b"<x/>"


@pytest.mark.asyncio
async def test_send_file_wraps_smtp_errors(monkeypatch):
    class Boom(_FakeSMTP):
        def login(self, u, p):
            raise pt.smtplib.SMTPAuthenticationError(535, b"bad")

    monkeypatch.setattr(pt.smtplib, "SMTP_SSL", Boom)
    with pytest.raises(pt.PecError, match="SMTP"):
        await pt.send_file(CREDS, "sdi01@pec.fatturapa.it", "f.xml", "<x/>")


def test_extract_receipts_reads_xml_and_zip_attachments_and_ignores_others():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("IT01234567897_00002_NS_001.xml", _rc("IT01234567897_00002.xml"))
        zf.writestr("readme.txt", "x")
    raw = _sdi_message(
        "sdi07@pec.fatturapa.it",
        [
            ("IT01234567897_00001_RC_001.xml", _rc().encode()),
            ("bundle.zip", buf.getvalue()),
            ("daticert.xml", b"<pec/>"),
        ],
    )
    receipts, sender = pt._extract_receipts(raw)
    assert sender == "sdi07@pec.fatturapa.it"
    assert sorted(n for n, _ in receipts) == [
        "IT01234567897_00001_RC_001.xml",
        "IT01234567897_00002_NS_001.xml",
    ]


class _FakeIMAP:
    messages: dict[bytes, bytes] = {}
    flagged: list[bytes] = []

    def __init__(self, host, port, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, u, p):
        pass

    def select(self, folder, readonly=False):
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        if cmd == "search":
            return "OK", [b" ".join(self.messages)]
        if cmd == "fetch":
            return "OK", [(b"1 (RFC822 {n})", self.messages[args[0]])]
        if cmd == "store":
            _FakeIMAP.flagged.append(args[0])
            return "OK", [b""]
        raise AssertionError(cmd)


@pytest.mark.asyncio
async def test_poll_receipts_returns_attachments_marks_seen_and_learns_the_sdi_address(monkeypatch):
    _FakeIMAP.messages = {
        b"11": _sdi_message(
            "sdi07@pec.fatturapa.it", [("IT01234567897_00001_RC_001.xml", _rc().encode())]
        ),
        b"12": _sdi_message("sdi07@pec.fatturapa.it", []),
    }
    _FakeIMAP.flagged.clear()
    monkeypatch.setattr(pt.imaplib, "IMAP4_SSL", _FakeIMAP)
    result = await pt.poll_receipts(CREDS)
    assert [r.file_name for r in result.receipts] == ["IT01234567897_00001_RC_001.xml"]
    assert result.receipts[0].xml.startswith("<ns3:RicevutaConsegna")
    assert result.sdi_reply_address == "sdi07@pec.fatturapa.it" and result.skipped == 1
    assert sorted(_FakeIMAP.flagged) == [b"11", b"12"]


def test_build_message_subject_is_the_file_stem():
    msg = pt.build_message(CREDS, "sdi01@pec.fatturapa.it", "IT01234567897_0000A.xml", "<x/>")
    assert msg["Subject"] == "IT01234567897_0000A"
    assert email.message_from_bytes(msg.as_bytes())["To"] == "sdi01@pec.fatturapa.it"


def test_extract_receipts_sees_through_the_pec_busta_di_trasporto():
    """PEC providers wrap the SDI message: outer From is the provider's
    posta-certificata address with "Per conto di: sdiNN@…" as display name,
    and the original message travels as a postacert.eml attachment."""
    inner = email.message_from_bytes(
        _sdi_message("sdi07@pec.fatturapa.it", [("IT01234567897_00001_RC_001.xml", _rc().encode())])
    )
    outer = EmailMessage()
    outer["From"] = '"Per conto di: sdi07@pec.fatturapa.it" <posta-certificata@pec.aruba.it>'
    outer["To"] = CREDS.address
    outer["Subject"] = "POSTA CERTIFICATA: RICEZIONE"
    outer.set_content("Messaggio di posta certificata")
    outer.add_attachment(
        b"<daticert/>", maintype="application", subtype="xml", filename="daticert.xml"
    )
    outer.add_attachment(inner, filename="postacert.eml")
    receipts, sender = pt._extract_receipts(outer.as_bytes())
    assert sender == "sdi07@pec.fatturapa.it"
    assert [n for n, _ in receipts] == ["IT01234567897_00001_RC_001.xml"]
