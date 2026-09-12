"""PEC transport for the SDI (spec §1.3, "Posta Elettronica Certificata").

The clinic's own PEC mailbox is the channel: the FPR12 file goes as an
attachment to the SDI mailbox (``sdi01@pec.fatturapa.it`` for the first
message; the SDI then answers from a dedicated ``sdiNN@pec.fatturapa.it``
address that must be used from then on), and the receipts (RC / NS / MC)
come back as XML attachments to the same mailbox.

Plain ``smtplib`` / ``imaplib`` from the standard library, run in the
default executor so the worker never blocks the event loop and no new
dependency is needed. Nothing here touches the database.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import re
import smtplib
import ssl
import zipfile
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from functools import partial
from io import BytesIO

SDI_DOMAIN = "pec.fatturapa.it"
_RECEIPT_NAME = re.compile(
    r"^IT[A-Z0-9]{1,28}_[A-Za-z0-9]{1,10}_(RC|NS|MC|MT|AT|NE|DT|EC)_[A-Za-z0-9]{1,3}\.xml$", re.I
)


class PecError(RuntimeError):
    pass


@dataclass(frozen=True)
class PecCredentials:
    address: str  # the clinic's PEC address (From)
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    username: str
    password: str
    imap_folder: str = "INBOX"


@dataclass
class InboundReceipt:
    uid: bytes
    file_name: str
    xml: str
    sender: str


@dataclass
class PollResult:
    receipts: list[InboundReceipt] = field(default_factory=list)
    sdi_reply_address: str | None = None  # the dedicated SDI mailbox, if it answered
    skipped: int = 0  # SDI messages without a receipt attachment


def build_message(creds: PecCredentials, to_address: str, file_name: str, xml: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = creds.address
    msg["To"] = to_address
    msg["Subject"] = file_name.rsplit(".", 1)[0]
    msg["Message-ID"] = make_msgid(domain=creds.address.rsplit("@", 1)[-1] or None)
    msg.set_content("Fattura elettronica in allegato.")
    msg.add_attachment(
        xml.encode("utf-8"), maintype="application", subtype="xml", filename=file_name
    )
    return msg


def _send_sync(creds: PecCredentials, to_address: str, file_name: str, xml: str) -> str:
    msg = build_message(creds, to_address, file_name, xml)
    context = ssl.create_default_context()
    try:
        if creds.smtp_port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                creds.smtp_host, creds.smtp_port, timeout=30, context=context
            )
        else:
            server = smtplib.SMTP(creds.smtp_host, creds.smtp_port, timeout=30)
            server.starttls(context=context)
        with server:
            server.login(creds.username, creds.password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise PecError(f"SMTP: {exc}") from exc
    return msg["Message-ID"] or ""


async def send_file(creds: PecCredentials, to_address: str, file_name: str, xml: str) -> str:
    """Send one FPR12 file; returns the outgoing Message-ID."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_send_sync, creds, to_address, file_name, xml))


_SDI_ADDRESS = re.compile(r"[a-z0-9._-]+@" + re.escape(SDI_DOMAIN), re.I)


def _sdi_sender(msg: email.message.Message) -> str:
    """The SDI address a message came from, seen through the PEC envelope.

    A PEC provider delivers the SDI's message inside a *busta di trasporto*:
    ``From: "Per conto di: sdi07@pec.fatturapa.it" <posta-certificata@…>``
    with the original message attached as ``postacert.eml``. So the address
    is looked for in the outer From header (display name included) and in
    the From of any embedded message; ``parseaddr`` alone would only see
    the provider's mailbox.
    """
    candidates = [str(msg.get("From", ""))]
    for part in msg.walk():
        if part.get_content_type() == "message/rfc822":
            for inner in part.get_payload():
                candidates.append(str(inner.get("From", "")))
    for header in candidates:
        m = _SDI_ADDRESS.search(header)
        if m:
            return m.group(0).lower()
    return parseaddr(msg.get("From", ""))[1].lower()


def _extract_receipts(raw: bytes) -> tuple[list[tuple[str, str]], str]:
    """(file_name, xml) pairs found in a message + the SDI sender address.

    ``walk()`` descends into ``message/rfc822`` parts, so attachments of
    the PEC-enveloped ``postacert.eml`` are found too.
    """
    msg = email.message_from_bytes(raw)
    sender = _sdi_sender(msg)
    out: list[tuple[str, str]] = []
    for part in msg.walk():
        name = part.get_filename() or ""
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(BytesIO(payload)) as zf:
                    for inner in zf.namelist():
                        if _RECEIPT_NAME.match(inner.rsplit("/", 1)[-1]):
                            out.append(
                                (
                                    inner.rsplit("/", 1)[-1],
                                    zf.read(inner).decode("utf-8", "replace"),
                                )
                            )
            except zipfile.BadZipFile:
                continue
        elif _RECEIPT_NAME.match(name):
            out.append((name, payload.decode("utf-8", "replace")))
    return out, sender


def _poll_sync(creds: PecCredentials, *, limit: int = 50) -> PollResult:
    result = PollResult()
    try:
        box = imaplib.IMAP4_SSL(creds.imap_host, creds.imap_port, timeout=30)
        with box:
            box.login(creds.username, creds.password)
            box.select(creds.imap_folder)
            status, data = box.uid("search", None, "UNSEEN", "FROM", SDI_DOMAIN)
            if status != "OK":
                raise PecError(f"IMAP search failed: {status}")
            uids = data[0].split()[:limit] if data and data[0] else []
            for uid in uids:
                status, parts = box.uid("fetch", uid, "(RFC822)")
                if status != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                receipts, sender = _extract_receipts(parts[0][1])
                if sender.endswith("@" + SDI_DOMAIN) and sender != f"sdi01@{SDI_DOMAIN}":
                    result.sdi_reply_address = sender
                if not receipts:
                    result.skipped += 1
                for file_name, xml in receipts:
                    result.receipts.append(
                        InboundReceipt(uid=uid, file_name=file_name, xml=xml, sender=sender)
                    )
                box.uid("store", uid, "+FLAGS", "(\\Seen)")
    except (imaplib.IMAP4.error, OSError) as exc:
        raise PecError(f"IMAP: {exc}") from exc
    return result


async def poll_receipts(creds: PecCredentials, *, limit: int = 50) -> PollResult:
    """Fetch unseen SDI messages, return their receipt attachments, mark them seen."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_poll_sync, creds, limit=limit))


def _test_sync(creds: PecCredentials) -> dict[str, str]:
    out: dict[str, str] = {}
    context = ssl.create_default_context()
    try:
        if creds.smtp_port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                creds.smtp_host, creds.smtp_port, timeout=20, context=context
            )
        else:
            server = smtplib.SMTP(creds.smtp_host, creds.smtp_port, timeout=20)
            server.starttls(context=context)
        with server:
            server.login(creds.username, creds.password)
        out["smtp"] = "ok"
    except (smtplib.SMTPException, OSError) as exc:
        out["smtp"] = f"error: {exc}"
    try:
        box = imaplib.IMAP4_SSL(creds.imap_host, creds.imap_port, timeout=20)
        with box:
            box.login(creds.username, creds.password)
            status, _ = box.select(creds.imap_folder, readonly=True)
            out["imap"] = (
                "ok" if status == "OK" else f"error: folder {creds.imap_folder} ({status})"
            )
    except (imaplib.IMAP4.error, OSError) as exc:
        out["imap"] = f"error: {exc}"
    return out


async def test_connection(creds: PecCredentials) -> dict[str, str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_test_sync, creds))
