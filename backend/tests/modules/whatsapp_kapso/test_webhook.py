"""whatsapp_kapso public webhook tests (signature, routing, inbound)."""

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password
from app.modules.notifications.models import CommunicationMessage
from app.modules.whatsapp_kapso.models import WhatsappKapsoSettings

WEBHOOK = "/api/v1/whatsapp_kapso/webhook"


async def _settings(db, clinic_id, *, pnid, secret):
    db.add(
        WhatsappKapsoSettings(
            clinic_id=clinic_id,
            api_key_encrypted=encrypt_password("k"),
            phone_number_id=pnid,
            webhook_secret_encrypted=encrypt_password(secret),
            is_active=True,
        )
    )
    await db.commit()


def _signed(payload: dict, secret: str) -> tuple[bytes, str]:
    raw = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


@pytest.mark.asyncio
async def test_inbound_records_reply(client: AsyncClient, db_session: AsyncSession, test_patient):
    await _settings(db_session, test_patient.clinic_id, pnid="PNID1", secret="whsec")
    payload = {
        "phone_number_id": "PNID1",
        "message": {
            "id": "wamid.in.99",
            "from": test_patient.phone,
            "type": "text",
            "text": {"body": "Confirmo mi cita"},
            "kapso": {"direction": "inbound", "content": "Confirmo mi cita"},
        },
    }
    raw, sig = _signed(payload, "whsec")
    resp = await client.post(
        WEBHOOK,
        content=raw,
        headers={"X-Webhook-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    row = (
        await db_session.execute(
            select(CommunicationMessage).where(CommunicationMessage.dedup_key == "wamid.in.99")
        )
    ).scalar_one()
    assert row.direction == "inbound"
    assert row.body_text == "Confirmo mi cita"
    assert row.patient_id == test_patient.id


@pytest.mark.asyncio
async def test_bad_signature_rejected(client: AsyncClient, db_session: AsyncSession, test_clinic):
    await _settings(db_session, test_clinic.id, pnid="PNID2", secret="realsecret")
    payload = {
        "phone_number_id": "PNID2",
        "message": {"id": "x", "kapso": {"direction": "inbound"}},
    }
    raw = json.dumps(payload).encode()
    resp = await client.post(WEBHOOK, content=raw, headers={"X-Webhook-Signature": "deadbeef"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unknown_number_accepted_and_ignored(client: AsyncClient):
    raw = json.dumps({"phone_number_id": "UNKNOWN", "message": {}}).encode()
    resp = await client.post(WEBHOOK, content=raw, headers={"X-Webhook-Signature": "whatever"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delivery_status_updates_message(
    client: AsyncClient, db_session: AsyncSession, test_patient
):
    await _settings(db_session, test_patient.clinic_id, pnid="PNID3", secret="s3")
    # an outbound message awaiting a delivery receipt
    sent = CommunicationMessage(
        clinic_id=test_patient.clinic_id,
        channel="whatsapp",
        to_address=test_patient.phone,
        patient_id=test_patient.id,
        template_key="appointment_reminder",
        status="sent",
        provider="whatsapp_kapso",
        provider_message_id="wamid.out.1",
    )
    db_session.add(sent)
    await db_session.commit()

    payload = {
        "phone_number_id": "PNID3",
        "message": {"id": "wamid.out.1", "kapso": {"direction": "outbound", "status": "delivered"}},
    }
    raw, sig = _signed(payload, "s3")
    resp = await client.post(WEBHOOK, content=raw, headers={"X-Webhook-Signature": sig})
    assert resp.status_code == 200
    await db_session.refresh(sent)
    assert sent.status == "delivered"
    assert sent.delivered_at is not None


@pytest.mark.asyncio
async def test_another_clinic_reusing_the_phone_number_id_does_not_break_the_webhook(
    client: AsyncClient, db_session: AsyncSession, test_patient
):
    """Clinic B saving clinic A's ``phone_number_id`` must not cut off clinic A (#972).

    ``phone_number_id`` is not unique and ``resolve_by_phone_number_id``
    used ``scalar_one_or_none``: once a second clinic saved the same id (a
    copy-paste or a typo), every Kapso webhook for it raised
    ``MultipleResultsFound`` before the signature was even checked, so
    clinic A's replies and receipts stopped.
    """
    from uuid import uuid4

    from app.core.auth.models import Clinic

    other = Clinic(id=uuid4(), name="Other clinic", tax_id="B00000000", settings={})
    db_session.add(other)
    await db_session.commit()
    await _settings(db_session, test_patient.clinic_id, pnid="SHARED", secret="secret-a")
    await _settings(db_session, other.id, pnid="SHARED", secret="secret-b")

    payload = {
        "phone_number_id": "SHARED",
        "message": {
            "id": "wamid.shared.1",
            "from": test_patient.phone,
            "type": "text",
            "text": {"body": "Hola"},
            "kapso": {"direction": "inbound", "content": "Hola"},
        },
    }
    raw, sig = _signed(payload, "secret-a")
    resp = await client.post(
        WEBHOOK,
        content=raw,
        headers={"X-Webhook-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    row = (
        await db_session.execute(
            select(CommunicationMessage).where(CommunicationMessage.dedup_key == "wamid.shared.1")
        )
    ).scalar_one()
    assert row.clinic_id == test_patient.clinic_id

    # A signature that matches neither clinic is still refused.
    raw, sig = _signed(payload, "not-a-secret")
    resp = await client.post(WEBHOOK, content=raw, headers={"X-Webhook-Signature": sig})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_saving_a_phone_number_id_another_clinic_uses_is_409(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    from uuid import uuid4

    from app.core.auth.models import Clinic

    other = Clinic(id=uuid4(), name="Other clinic", tax_id="B00000001", settings={})
    db_session.add(other)
    await db_session.commit()
    await _settings(db_session, other.id, pnid="TAKEN", secret="s")

    resp = await client.put(
        "/api/v1/whatsapp_kapso/settings",
        json={"phone_number_id": "TAKEN"},
        headers=auth_headers,
    )
    assert resp.status_code == 409, resp.text


async def _post_inbound(client: AsyncClient, wamid: str, from_addr: str) -> int:
    payload = {
        "phone_number_id": "PNIDH",
        "message": {
            "id": wamid,
            "from": from_addr,
            "type": "text",
            "text": {"body": "Ok"},
            "kapso": {"direction": "inbound", "content": "Ok"},
        },
    }
    raw, sig = _signed(payload, "whsec")
    resp = await client.post(
        WEBHOOK,
        content=raw,
        headers={"X-Webhook-Signature": sig, "Content-Type": "application/json"},
    )
    return resp.status_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stored", "sent"),
    [
        ("34600112233", "34600112233"),  # identical strings: used to 500
        ("600112233", "34600112233"),  # suffix match: used to pick one at random
    ],
)
async def test_inbound_from_a_shared_household_number_links_nobody(
    client: AsyncClient, db_session: AsyncSession, test_clinic, stored: str, sent: str
):
    """A reply from a number two patients share is not pinned on either (#965).

    Parents and children often share one mobile. The exact lookup used
    ``scalar_one_or_none`` (MultipleResultsFound → 500, so Kapso retried and
    the reply was never stored) and the suffix lookup took ``.first()``
    with no order, attaching the reply and the 24h window to whichever
    sibling the database returned.
    """
    from app.modules.patients.models import Patient

    await _settings(db_session, test_clinic.id, pnid="PNIDH", secret="whsec")
    for first in ("Ana", "Leo"):
        db_session.add(
            Patient(clinic_id=test_clinic.id, first_name=first, last_name="Ruiz", phone=stored)
        )
    await db_session.commit()

    assert await _post_inbound(client, "wamid.house.1", sent) == 200
    row = (
        await db_session.execute(
            select(CommunicationMessage).where(CommunicationMessage.dedup_key == "wamid.house.1")
        )
    ).scalar_one()
    assert row.patient_id is None
    assert row.body_text == "Ok"
