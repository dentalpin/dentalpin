"""A receipt is marked seen only once it is saved: the poll reads only UNSEEN."""

from email.message import EmailMessage

import pytest

from app.modules.sdi_it.services import pec_transport as pt
from app.modules.sdi_it.services import submission_queue as q

from .test_queue import NS, _setup

FILE = "IT01234567897_00001.xml"


def _message(root: str, kind: str) -> bytes:
    xml = (
        f'<ns3:{root} xmlns:ns3="{NS}"><IdentificativoSdI>9</IdentificativoSdI>'
        f"<NomeFile>{FILE}</NomeFile></ns3:{root}>"
    )
    msg = EmailMessage()
    msg["From"] = "Sistema di Interscambio <sdi07@pec.fatturapa.it>"
    msg.set_content("ricevuta")
    msg.add_attachment(
        xml.encode(),
        maintype="application",
        subtype="xml",
        filename=f"IT01234567897_00001_{kind}_001.xml",
    )
    return msg.as_bytes()


class _Mailbox:
    """The part of RFC 3501 that matters: fetching a body without PEEK sets Seen."""

    def __init__(self, messages: dict[bytes, bytes]) -> None:
        self.messages = messages
        self.seen: set[bytes] = set()
        self.broken: set[bytes] = set()
        self.store_fails = False

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, *a):
        pass

    def select(self, *a, **k):
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        if cmd == "search":
            return "OK", [b" ".join(u for u in self.messages if u not in self.seen)]
        if cmd == "fetch":
            if args[0] in self.broken:
                raise OSError("connection reset")
            if "PEEK" not in args[1]:
                self.seen.add(args[0])
            return "OK", [(b"1 (BODY[] {n})", self.messages[args[0]])]
        if cmd == "store":
            if self.store_fails:
                raise OSError("connection reset")
            self.seen.update(args[0].split(b","))
            return "OK", [b""]
        raise AssertionError(cmd)


async def _exported(db, monkeypatch, box):
    clinic, _, rec = await _setup(db)
    rec.state = "exported"
    await db.commit()
    monkeypatch.setattr(pt.imaplib, "IMAP4_SSL", box)
    return clinic.id, rec


@pytest.mark.asyncio
async def test_a_dropped_connection_loses_no_receipt(db_session, monkeypatch):
    box = _Mailbox({b"11": _message("RicevutaConsegna", "RC"), b"12": b"From: x\r\n\r\n"})
    box.broken = {b"12"}
    clinic_id, rec = await _exported(db_session, monkeypatch, box)

    await q.process_clinic(db_session, clinic_id)
    box.broken = set()
    await q.process_clinic(db_session, clinic_id)

    await db_session.refresh(rec)
    assert rec.state == "delivered"
    assert box.seen == {b"11", b"12"}


@pytest.mark.asyncio
async def test_a_failed_save_leaves_the_receipt_unseen(db_session, monkeypatch):
    box = _Mailbox({b"11": _message("RicevutaConsegna", "RC")})
    clinic_id, _ = await _exported(db_session, monkeypatch, box)

    async def fails(*a, **k):
        raise RuntimeError("database went away")

    monkeypatch.setattr(q, "apply_receipt", fails)
    with pytest.raises(RuntimeError):
        await q.process_clinic(db_session, clinic_id)
    assert box.seen == set()


@pytest.mark.asyncio
async def test_a_receipt_read_again_is_not_applied_again(db_session, monkeypatch):
    """When marking fails the next poll returns it; a scarto may be requeued by then."""
    box = _Mailbox({b"11": _message("NotificaScarto", "NS")})
    box.store_fails = True
    clinic_id, rec = await _exported(db_session, monkeypatch, box)

    first = await q.process_clinic(db_session, clinic_id)
    again = await q.process_clinic(db_session, clinic_id)

    await db_session.refresh(rec)
    assert rec.state == "rejected"
    assert (first["receipts"], again["receipts"], again["unmatched"]) == (1, 0, 1)
