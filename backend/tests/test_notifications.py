"""Tests for the notifications module."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    SendStatus,
    channel_registry,
)
from app.modules.notifications.models import (
    NotificationTemplate,
)
from app.modules.notifications.service import NotificationService


@pytest_asyncio.fixture
async def whatsapp_channel():
    """A fake connected WhatsApp adapter, so 'whatsapp' is available."""

    class FakeWhatsApp:
        channel = Channel.WHATSAPP
        adapter_name = "fake_whatsapp_api_test"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_whatsapp", provider_message_id="wamid.api"
            )

    adapter = FakeWhatsApp()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("fake_whatsapp_api_test")


@pytest.mark.asyncio
async def test_available_channels_email_only_by_default(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    """#207: without a configured vendor channel only email is available —
    the WhatsApp conversation card gates on this list."""
    response = await client.get("/api/v1/notifications/channels", headers=auth_headers)
    assert response.status_code == 200, response.text
    available = response.json()["data"]["available"]
    assert "email" in available
    assert "whatsapp" not in available


@pytest.mark.asyncio
async def test_get_clinic_settings(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """Test getting clinic notification settings."""
    response = await client.get(
        "/api/v1/notifications/settings",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Should have default settings
    assert "settings" in data
    assert "appointment_confirmation" in data["settings"]
    assert data["settings"]["appointment_confirmation"]["enabled"] is True


@pytest.mark.asyncio
async def test_update_clinic_settings(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """Test updating clinic notification settings."""
    update_data = {
        "settings": {
            "appointment_confirmation": {"auto_send": False},
            "welcome": {"enabled": False},
        }
    }

    response = await client.put(
        "/api/v1/notifications/settings",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Check updated values
    assert data["settings"]["appointment_confirmation"]["auto_send"] is False
    assert data["settings"]["welcome"]["enabled"] is False


@pytest.mark.asyncio
async def test_get_patient_preferences(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_patient
):
    """Test getting patient notification preferences."""
    response = await client.get(
        f"/api/v1/notifications/preferences/patient/{test_patient.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Should have default preferences
    assert data["email_enabled"] is True
    assert "preferences" in data


@pytest.mark.asyncio
async def test_update_patient_preferences(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_patient
):
    """Test updating patient notification preferences."""
    update_data = {
        "email_enabled": False,
        "preferences": {"appointment_confirmation": True, "appointment_reminder": False},
    }

    response = await client.put(
        f"/api/v1/notifications/preferences/patient/{test_patient.id}",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["email_enabled"] is False
    assert data["preferences"]["appointment_reminder"] is False


@pytest.mark.asyncio
async def test_list_email_logs(client: AsyncClient, auth_headers: dict, test_clinic):
    """Test listing email logs."""
    response = await client.get(
        "/api/v1/notifications/logs",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient, auth_headers: dict, test_clinic):
    """Test listing email templates."""
    response = await client.get(
        "/api/v1/notifications/templates",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_test_email_endpoint(client: AsyncClient, auth_headers: dict, test_clinic):
    """Test the test email endpoint."""
    response = await client.post(
        "/api/v1/notifications/test",
        json={"to_email": "test@example.com"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # In test mode, should use console provider
    assert data["provider"] == "console"
    assert data["success"] is True


@pytest.mark.asyncio
async def test_should_send_notification(db_session: AsyncSession, test_clinic):
    """Test the should_send_notification check."""
    # Without any settings, should return True for auto_send types
    should_send, reason = await NotificationService.should_send_notification(
        db_session,
        test_clinic.id,
        "appointment_confirmation",
    )

    # With default settings, should send
    assert reason in ["ok", "disabled_at_clinic_level", "manual_send_required"]


@pytest.mark.asyncio
async def test_manual_send_requires_patient_email(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """Test that manual send requires a patient with email."""
    response = await client.post(
        "/api/v1/notifications/send",
        json={
            "notification_type": "welcome",
            # No patient_id provided
        },
        headers=auth_headers,
    )

    # Should fail because no recipient can be determined
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_custom_template(client: AsyncClient, auth_headers: dict, test_clinic):
    """Test creating a custom email template."""
    template_data = {
        "template_key": "custom_test",
        "locale": "es",
        "subject": "Test Subject",
        "body_html": "<html><body>Test</body></html>",
        "description": "Test template",
    }

    response = await client.post(
        "/api/v1/notifications/templates",
        json=template_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]

    assert data["template_key"] == "custom_test"
    assert data["is_system"] is False


@pytest.mark.asyncio
async def test_cannot_delete_system_template(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """Test that system templates cannot be deleted."""
    # First create a system template in DB
    from uuid import uuid4

    system_template = NotificationTemplate(
        id=uuid4(),
        clinic_id=None,
        template_key="system_test",
        locale="es",
        subject="System Template",
        body_html="<p>System</p>",
        is_system=True,
    )
    db_session.add(system_template)
    await db_session.commit()
    await db_session.refresh(system_template)

    # Try to delete
    response = await client.delete(
        f"/api/v1/notifications/templates/{system_template.id}",
        headers=auth_headers,
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Event handlers queue on the publisher's session (issue #183)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creating_a_patient_queues_the_welcome_message(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """The handler used to re-read the patient from its own session, in a
    task racing the request's commit. The row was invisible there, so it
    returned early and the welcome message was never queued."""
    from sqlalchemy import select

    from app.modules.notifications.models import CommunicationMessage

    res = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={
            "first_name": "Nuevo",
            "last_name": "Paciente",
            "email": "nuevo@paciente.example.com",
        },
    )
    assert res.status_code == 201, res.text

    queued = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.to_address == "nuevo@paciente.example.com"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(queued) == 1
    assert queued[0].template_key == "welcome"
    assert queued[0].status in ("queued", "skipped")


@pytest.mark.asyncio
async def test_nothing_is_queued_when_the_request_rolls_back(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """No welcome message for a patient that was never created."""
    from sqlalchemy import select

    from app.modules.notifications.models import CommunicationMessage
    from app.modules.patients.service import PatientService

    await PatientService.create_patient(
        db_session,
        test_clinic.id,
        {"first_name": "Fantasma", "last_name": "Nunca", "email": "fantasma@paciente.example.com"},
    )
    await db_session.rollback()

    queued = await db_session.scalar(
        select(CommunicationMessage.id).where(
            CommunicationMessage.to_address == "fantasma@paciente.example.com"
        )
    )
    assert queued is None


# ---------------------------------------------------------------------------
# #287 — clinic preferred channel + manual channels (settings API)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_response_includes_channel_fields(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    """GET returns the new clinic-wide channel fields + computed
    available_channels (email only while no WhatsApp adapter is connected)."""
    response = await client.get("/api/v1/notifications/settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["preferred_channel"] == "email"
    assert data["fallback_enabled"] is True
    assert data["manual_channels"] == ["email"]
    assert "email" in data["available_channels"]
    assert "whatsapp" not in data["available_channels"]
    # new types present in the per-type defaults
    for key in ("invoice_sent", "budget_reminder", "recall_reminder"):
        assert key in data["settings"]
    assert data["settings"]["invoice_sent"]["auto_send"] is False
    assert data["settings"]["budget_reminder"]["auto_send"] is True


@pytest.mark.asyncio
async def test_settings_put_preferred_whatsapp_not_available_is_422(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    """Preferred channel must be available for this clinic (Kapso connected)."""
    response = await client.put(
        "/api/v1/notifications/settings",
        json={"preferred_channel": "whatsapp"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_settings_put_manual_channel_not_available_is_422(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    response = await client.put(
        "/api/v1/notifications/settings",
        json={"manual_channels": ["whatsapp"]},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_settings_put_inserts_preferred_into_manual_channels(
    client: AsyncClient, auth_headers: dict, test_clinic, whatsapp_channel
):
    """Server keeps the invariant preferred ∈ manual_channels when the
    client omits it, so staff can resend on the preferred wire."""
    response = await client.put(
        "/api/v1/notifications/settings",
        json={"preferred_channel": "whatsapp", "manual_channels": ["email"]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["preferred_channel"] == "whatsapp"
    assert set(data["manual_channels"]) == {"whatsapp", "email"}
    assert "whatsapp" in data["available_channels"]

    # persisted — a plain GET returns the same values
    response = await client.get("/api/v1/notifications/settings", headers=auth_headers)
    data = response.json()["data"]
    assert data["preferred_channel"] == "whatsapp"
    assert set(data["manual_channels"]) == {"whatsapp", "email"}


@pytest.mark.asyncio
async def test_new_preference_rows_default_whatsapp_enabled(
    client: AsyncClient, auth_headers: dict, test_patient
):
    """Bug 11: WhatsApp is opt-out like email — new rows default enabled."""
    response = await client.get(
        f"/api/v1/notifications/preferences/patient/{test_patient.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["whatsapp_enabled"] is True


# ---------------------------------------------------------------------------
# #287 — manual send with explicit channels
# ---------------------------------------------------------------------------


async def _phone_only_patient(db_session: AsyncSession, clinic_id):
    from uuid import uuid4

    from app.modules.patients.models import Patient

    patient = Patient(
        id=uuid4(),
        clinic_id=clinic_id,
        first_name="Solo",
        last_name="Telefono",
        phone="+34600000001",
    )
    db_session.add(patient)
    await db_session.commit()
    return patient


@pytest.mark.asyncio
async def test_manual_send_whatsapp_phone_only_patient_is_not_400(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic,
    whatsapp_channel,
):
    """A phone-only patient must not 400 on a WhatsApp send. Without an
    approved HSM the outbox row is an explicit skip on the WhatsApp wire."""
    patient = await _phone_only_patient(db_session, test_clinic.id)
    # clinic prefers WhatsApp so the skip row is labeled with that channel
    put = await client.put(
        "/api/v1/notifications/settings",
        json={"preferred_channel": "whatsapp"},
        headers=auth_headers,
    )
    assert put.status_code == 200

    response = await client.post(
        "/api/v1/notifications/send",
        json={
            "notification_type": "welcome",
            "patient_id": str(patient.id),
            "channels": ["whatsapp"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is False  # no approved HSM → explicit skip, not 400
    assert data["log_id"] is not None

    from sqlalchemy import select

    from app.modules.notifications.models import CommunicationMessage

    row = (
        await db_session.execute(
            select(CommunicationMessage).where(CommunicationMessage.id == data["log_id"])
        )
    ).scalar_one()
    assert row.status == "skipped"
    assert row.error_message == "no_viable_channel"
    assert row.channel == "whatsapp"


@pytest.mark.asyncio
async def test_manual_send_whatsapp_with_approved_hsm_queues(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic,
    whatsapp_channel,
):
    """With Kapso connected and an approved HSM, the same phone-only send
    queues a WhatsApp message addressed to the patient's phone."""
    patient = await _phone_only_patient(db_session, test_clinic.id)
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            channel="whatsapp",
            template_key="welcome",
            locale="es",
            provider_template_name="hsm_welcome",
            provider_template_status="approved",
            is_system=False,
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/notifications/send",
        json={
            "notification_type": "welcome",
            "patient_id": str(patient.id),
            "channels": ["whatsapp"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True

    from sqlalchemy import select

    from app.modules.notifications.models import CommunicationMessage

    row = (
        await db_session.execute(
            select(CommunicationMessage).where(CommunicationMessage.id == data["log_id"])
        )
    ).scalar_one()
    assert row.status == "queued"
    assert row.channel == "whatsapp"
    assert row.to_address == patient.phone


@pytest.mark.asyncio
async def test_manual_send_without_channels_keeps_email_behaviour(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic,
):
    """Legacy path: no channels field ⇒ email recipient still required."""
    patient = await _phone_only_patient(db_session, test_clinic.id)

    response = await client.post(
        "/api/v1/notifications/send",
        json={"notification_type": "welcome", "patient_id": str(patient.id)},
        headers=auth_headers,
    )
    assert response.status_code == 400
