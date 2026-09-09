"""sms_gateway: encrypted settings, masked views, honest placeholder, isolation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.channels import Channel, channel_registry
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import NotificationTemplate
from app.modules.notifications.service import NotificationService
from app.modules.sms_gateway.adapter import SmsGatewayAdapter
from app.modules.sms_gateway.schemas import mask_settings
from app.modules.sms_gateway.service import SmsGatewayService

SID = "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN = "supersecrettoken"


async def _configure(db, clinic_id, **kw):
    data = {"provider": "log", "is_active": True}
    data.update(kw)
    return await SmsGatewayService.upsert_settings(db, clinic_id, data)


@pytest.mark.asyncio
async def test_settings_roundtrip_masked(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id
    row = await _configure(db_session, clinic_id, account_sid=SID, auth_token=TOKEN)
    out = mask_settings(row)
    assert out.has_account_sid is True
    assert out.has_auth_token is True
    assert out.provider == "log"
    dumped = out.model_dump_json()
    assert SID not in dumped
    assert TOKEN not in dumped
    assert row.account_sid_encrypted != SID
    assert row.auth_token_encrypted != TOKEN


@pytest.mark.asyncio
async def test_adapter_log_provider_sends(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.notifications.channels import OutboundMessage

    clinic_id = test_clinic.id
    await _configure(db_session, clinic_id)
    adapter = SmsGatewayAdapter()
    assert adapter.channel == Channel.SMS
    assert await adapter.supports(db_session, clinic_id) is True
    result = await adapter.send(
        db_session,
        OutboundMessage(
            channel=Channel.SMS,
            to_address="+34666123456",
            clinic_id=clinic_id,
            template_key="appointment_confirmation",
            message_kind="session",
            body_text="hola",
        ),
    )
    assert result.status.value == "sent"


@pytest.mark.asyncio
async def test_unimplemented_provider_fails_honestly(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.notifications.channels import OutboundMessage

    clinic_id = test_clinic.id
    await _configure(db_session, clinic_id, provider="twilio")
    adapter = SmsGatewayAdapter()
    result = await adapter.send(
        db_session,
        OutboundMessage(
            channel=Channel.SMS,
            to_address="+34666123456",
            clinic_id=clinic_id,
            template_key="appointment_confirmation",
        ),
    )
    assert result.status.value == "failed"
    assert "not implemented" in (result.error_message or "")


@pytest.mark.asyncio
async def test_gateway_end_to_end_over_sms(db_session: AsyncSession, test_patient):
    """Real adapter registered: an sms enqueue queues (log placeholder)."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_phone = test_patient.phone
    await _configure(db_session, clinic_id)
    channel_registry.register(SmsGatewayAdapter())
    try:
        msg = await NotificationGateway.enqueue(
            db_session,
            clinic_id,
            "appointment_confirmation",
            context={},
            patient_id=patient_id,
            channels=["sms"],
        )
    finally:
        channel_registry.unregister("sms_gateway")
    assert msg.status == "queued"
    assert msg.channel == "sms"
    assert msg.to_address == patient_phone


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999994",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()
    await _configure(db_session, other.id)
    assert await SmsGatewayService.get_settings(db_session, test_clinic.id) is None


# Every notification_type the gateway enqueues must have a seeded SMS
# template row (smg_0002 ROWS), or template-kind SMS dispatches with
# body_text=None (maintainer review on #384).
ENQUEUED_TYPES = {
    "appointment_confirmation",
    "appointment_reminder",
    "appointment_cancelled",
    "budget_sent",
    "budget_accepted",
    "budget_reminder",
    "invoice_sent",
    "welcome",
    "recall_reminder",
}


def _seed_rows():
    """Import the frozen seed table from the migration (no DB needed)."""
    import importlib.util

    path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "modules"
        / "sms_gateway"
        / "migrations"
        / "versions"
        / "smg_0002_seed_sms_templates.py"
    )
    spec = importlib.util.spec_from_file_location("smg_0002_seed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ROWS


@pytest.mark.asyncio
async def test_seed_rows_cover_all_enqueue_types(db_session: AsyncSession):
    """The smg_0002 seed table covers every enqueued type in es and en."""
    rows = _seed_rows()
    assert len(rows) == len(ENQUEUED_TYPES)
    covered = {key for key, _, _ in rows}
    assert covered == ENQUEUED_TYPES
    for key, es_body, en_body in rows:
        assert es_body.strip() and en_body.strip()


@pytest.mark.asyncio
async def test_sms_template_lookup_resolves_seeded_body(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The dispatch lookup (channel filter + system fallback) finds SMS bodies."""
    clinic_id = test_clinic.id
    assert (
        await NotificationService.get_template(
            db_session, clinic_id, "appointment_confirmation", "es", channel="sms"
        )
    ) is None

    db_session.add(
        NotificationTemplate(
            clinic_id=None,
            channel="sms",
            template_key="appointment_confirmation",
            locale="es",
            body_text="Su cita ha quedado confirmada.",
            is_system=True,
        )
    )
    await db_session.commit()
    found = await NotificationService.get_template(
        db_session, clinic_id, "appointment_confirmation", "es", channel="sms"
    )
    assert found is not None
    assert found.body_text == "Su cita ha quedado confirmada."


@pytest.mark.asyncio
async def test_providers_lists_registered_backends(client, auth_headers, test_clinic):
    """GET /providers answers the registered wire backends (issue #392)."""
    response = await client.get("/api/v1/sms_gateway/providers", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == ["log"]


@pytest.mark.asyncio
async def test_update_rejects_unregistered_provider(client, auth_headers, test_clinic):
    """PUT with a provider no backend implements is a loud 422, never a
    silent dead-end at send time (issue #392 review)."""
    response = await client.put(
        "/api/v1/sms_gateway/settings",
        json={"provider": "twilio", "is_active": True},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
    ok = await client.put(
        "/api/v1/sms_gateway/settings",
        json={"provider": "log", "is_active": True},
        headers=auth_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["provider"] == "log"
