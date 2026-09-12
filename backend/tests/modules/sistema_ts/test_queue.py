"""Worker: accepted / rejected / transport failure / credential pause."""

import pytest
from sqlalchemy import select

from app.modules.sistema_ts.models import SistemaTsDocument
from app.modules.sistema_ts.services import submission_queue as q
from app.modules.sistema_ts.services import ts_client

from ._fixtures import make_clinic, make_invoice, make_patient

OK = ts_client.TsResponse(esito=0, protocollo="15120210394302801", raw="<ok/>")
BAD = ts_client.TsResponse(
    esito=1,
    protocollo=None,
    messages=[{"codice": "E01", "descrizione": "CF non valido", "tipo": "E"}],
    raw="<bad/>",
)


@pytest.mark.asyncio
async def test_tick_syncs_and_sends(db_session, monkeypatch):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)
    await make_invoice(db_session, clinic, user, patient)
    await db_session.commit()
    sent = []

    async def fake_send(xml, *, environment, username, password, timeout=30.0):
        sent.append((environment, username, password))
        return OK

    monkeypatch.setattr(ts_client, "send", fake_send)
    counters = await q.process_clinic(db_session, clinic.id)
    assert counters == {"queued": 1, "accepted": 1, "rejected": 0, "failed": 0}
    assert sent == [("test", "PROVAX00X00X000Y", "Salve123")]
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    assert (
        doc.state == "accepted"
        and doc.protocollo == "15120210394302801"
        and doc.request_xml
        and doc.response_xml == "<ok/>"
    )


@pytest.mark.asyncio
async def test_rejection_is_terminal_with_messages(db_session, monkeypatch):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)
    await make_invoice(db_session, clinic, user, patient)
    await db_session.commit()

    async def fake_send(*a, **k):
        return BAD

    monkeypatch.setattr(ts_client, "send", fake_send)
    counters = await q.process_clinic(db_session, clinic.id)
    assert counters["rejected"] == 1
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    assert (
        doc.state == "rejected"
        and "E01" in doc.error_message
        and doc.messages[0]["codice"] == "E01"
    )


@pytest.mark.asyncio
async def test_transport_failure_backs_off_and_bad_credentials_pause(db_session, monkeypatch):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)
    await make_invoice(db_session, clinic, user, patient)
    await db_session.commit()

    async def boom(*a, **k):
        raise ts_client.TsClientError("HTTP: timeout")

    monkeypatch.setattr(ts_client, "send", boom)
    counters = await q.process_clinic(db_session, clinic.id)
    assert counters["failed"] == 1
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    assert doc.state == "pending" and doc.attempts == 1 and doc.next_attempt_at is not None
    await db_session.refresh(settings)
    assert settings.next_send_after is None  # a timeout does not pause the clinic

    async def denied(*a, **k):
        raise ts_client.TsClientError("HTTP 401: credenziali Sistema TS rifiutate")

    doc.next_attempt_at = None
    await db_session.commit()
    monkeypatch.setattr(ts_client, "send", denied)
    await q.process_clinic(db_session, clinic.id)
    await db_session.refresh(settings)
    assert settings.next_send_after is not None and "credenziali" in settings.last_error


@pytest.mark.asyncio
async def test_disabled_clinic_is_inert(db_session, monkeypatch):
    clinic, user, settings = await make_clinic(db_session, enabled=False)
    patient = await make_patient(db_session, clinic)
    await make_invoice(db_session, clinic, user, patient)
    await db_session.commit()

    async def never(*a, **k):
        raise AssertionError("must not send")

    monkeypatch.setattr(ts_client, "send", never)
    assert await q.process_clinic(db_session, clinic.id) == {
        "queued": 0,
        "accepted": 0,
        "rejected": 0,
        "failed": 0,
    }
