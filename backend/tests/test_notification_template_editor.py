"""Clinic-scoped template editing, rendering and default resolution."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.core.auth.models import Clinic, ClinicMembership
from app.core.email import email_service
from app.modules.notifications.channels import Channel, channel_registry
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import (
    NOTIFICATION_TYPES,
    ClinicChannelSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.notifications.service import NotificationService
from app.modules.notifications.template_variables import available_fields, example_context
from app.modules.whatsapp_manual.adapter import ManualWhatsAppAdapter

KEY = "appointment_reminder"
EDITOR = f"/api/v1/notifications/templates/editor/{KEY}"
EMAIL = {"channel": "email", "locale": "es"}
WHATSAPP = {"channel": "whatsapp", "locale": "es"}
COPY = {
    "subject": "Recordatorio — {{ patient_name }}",
    "body_html": "<p>Hola {{ patient_name }}. A las {{ appointment_time }}.</p>",
    "body_text": "A las {{ appointment_time }}.",
}


@pytest.fixture
def manual_adapter():
    adapter = ManualWhatsAppAdapter()
    previous = channel_registry.get_by_name(adapter.adapter_name)
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister(adapter.adapter_name)
    if previous:
        channel_registry.register(previous)


async def enable_manual(db, clinic):
    clinic.settings = {**(clinic.settings or {}), "country": "ES"}
    db.add(
        ClinicChannelSettings(
            clinic_id=clinic.id, channel="whatsapp", adapter_name="whatsapp_manual", is_enabled=True
        )
    )
    await db.flush()


async def test_editor_preview_uses_real_email_renderer_and_default(
    client, auth_headers, db_session, test_clinic
):
    test_clinic.timezone = "Europe/Madrid"
    res = await client.get(EDITOR, headers=auth_headers, params=EMAIL)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["editable"] and not data["has_override"] and data["default_locale"] == "es"
    variables = {item["key"]: item for item in data["variables"]}
    assert variables["appointment_time"]["example"] == "10:30"
    assert variables["checkin_url"]["optional"]
    assert "appointment_id" not in variables

    res = await client.post(f"{EDITOR}/preview", headers=auth_headers, params=EMAIL, json={})
    assert "Alex Example" in res.json()["data"]["body_html"]
    draft = await client.post(
        f"{EDITOR}/preview",
        headers=auth_headers,
        params=EMAIL,
        json={"content": {"body_html": "Sample {{ patient_name }}"}},
    )
    assert draft.json()["data"]["subject"] == res.json()["data"]["subject"]
    assert await db_session.scalar(select(func.count()).select_from(CommunicationMessage)) == 0

    res = await client.put(EDITOR, headers=auth_headers, params=EMAIL, json=COPY)
    assert res.status_code == 204, res.text
    res = await client.post(f"{EDITOR}/preview", headers=auth_headers, params=EMAIL, json={})
    context = example_context(KEY, "es", test_clinic)
    body = email_service.render_notification_html(COPY["body_html"], context, "es", strict=True)
    assert res.json()["data"] == {
        "subject": email_service.render_subject(COPY["subject"], context),
        "body_html": body,
        "body_text": "A las 10:30.",
    }
    assert await db_session.scalar(select(func.count()).select_from(CommunicationMessage)) == 0


async def test_editor_invalid_copy_leaves_saved_template_intact(client, auth_headers, test_clinic):
    res = await client.put(EDITOR, headers=auth_headers, params=EMAIL, json=COPY)
    assert res.status_code == 204, res.text
    cases = [
        ("Hello\n{{ appointment_tim }}", "unknown_variable", 2),
        ("Hello\n{% if %}", "invalid_jinja", 2),
        ("{% include 'base.html' %}", "unsupported_syntax", 1),
        ("{{ professional_name }}", "missing_value", 1),
    ]
    for text, code, line in cases:
        res = await client.put(
            EDITOR, headers=auth_headers, params=EMAIL, json={**COPY, "body_html": text}
        )
        assert res.status_code == 422, res.text
        detail = res.json()["detail"]
        assert (detail["code"], detail["field"], detail["line"]) == (code, "body_html", line)
    saved = await client.get(EDITOR, headers=auth_headers, params=EMAIL)
    assert saved.json()["data"]["current"] == COPY
    res = await client.post(
        f"{EDITOR}/preview",
        headers=auth_headers,
        params=EMAIL,
        json={
            "content": {**COPY, "body_html": "{{ professional_name | default('Team') }}"},
            "minimal": True,
        },
    )
    assert "Team" in res.json()["data"]["body_html"]
    assert "email-header" in res.json()["data"]["body_html"]


async def test_editor_scopes_copy_and_never_deletes_provider_mapping(
    client, auth_headers, db_session, test_clinic, manual_adapter
):
    await enable_manual(db_session, test_clinic)
    other = Clinic(id=uuid4(), name="Other Example Clinic", tax_id="B87654321")
    db_session.add(other)
    await db_session.flush()
    db_session.add_all(
        [
            NotificationTemplate(
                clinic_id=other.id,
                channel="email",
                template_key=KEY,
                locale="es",
                body_html="Other",
            ),
            NotificationTemplate(
                clinic_id=test_clinic.id,
                channel="email",
                template_key=KEY,
                locale="en",
                body_html="English",
            ),
            NotificationTemplate(
                clinic_id=test_clinic.id,
                channel="whatsapp",
                template_key=KEY,
                locale="es",
                provider_template_name="approved_meta_example",
                provider_template_status="approved",
            ),
        ]
    )
    await db_session.flush()
    missing = await client.get(EDITOR, headers=auth_headers, params=WHATSAPP)
    assert missing.json()["data"]["default_locale"] is None
    assert not missing.json()["data"]["has_override"]

    for query, body in [(EMAIL, COPY), (WHATSAPP, {"body_text": "{{ appointment_date }}"})]:
        res = await client.put(EDITOR, headers=auth_headers, params=query, json=body)
        assert res.status_code == 204, res.text

    res = await client.delete(EDITOR, headers=auth_headers, params=WHATSAPP)
    assert res.status_code == 204, res.text
    still = await NotificationService.get_clinic_template(
        db_session, test_clinic.id, KEY, "es", "whatsapp"
    )
    assert still.body_text is None and still.is_active
    assert (still.provider_template_name, still.provider_template_status) == (
        "approved_meta_example",
        "approved",
    )
    res = await client.delete(EDITOR, headers=auth_headers, params=EMAIL)
    assert res.status_code == 204, res.text
    assert (
        await NotificationService.get_clinic_template(
            db_session, test_clinic.id, KEY, "es", "email"
        )
        is None
    )
    assert (
        await NotificationService.get_clinic_template(
            db_session, test_clinic.id, KEY, "en", "email"
        )
        is not None
    )
    assert (
        await NotificationService.get_clinic_template(db_session, other.id, KEY, "es", "email")
        is not None
    )
    res = await client.get(EDITOR, headers=auth_headers, params=EMAIL)
    assert res.json()["data"]["default_locale"] == "es"


async def test_restore_preserves_prepared_draft_and_uses_existing_system_row(
    client, auth_headers, db_session, test_clinic, test_patient, manual_adapter
):
    await enable_manual(db_session, test_clinic)
    test_patient.phone = "+34666123456"
    db_session.add_all(
        [
            NotificationPreference(
                clinic_id=test_clinic.id,
                patient_id=test_patient.id,
                whatsapp_opt_in_at=datetime.now(UTC),
            ),
            NotificationTemplate(
                channel="whatsapp",
                template_key=KEY,
                locale="es",
                is_system=True,
                body_text="Default {{ patient_name }}",
            ),
        ]
    )
    await db_session.flush()
    edit = await client.put(
        EDITOR, headers=auth_headers, params=WHATSAPP, json={"body_text": "Hola {{ patient_name }}"}
    )
    assert edit.status_code == 204, edit.text
    preview = await client.post(f"{EDITOR}/preview", headers=auth_headers, params=WHATSAPP, json={})
    assert preview.json()["data"]["body_text"] == "Hola Alex Example"

    async def enqueue():
        return await NotificationGateway.enqueue(
            db_session,
            test_clinic.id,
            KEY,
            context={"patient_name": "Alex Example"},
            patient_id=test_patient.id,
            channels=["whatsapp"],
            force_send=True,
        )

    first = await enqueue()
    await NotificationGateway.dispatch_outbox(db_session)
    assert (
        first.status == "awaiting_manual" and first.body_text == preview.json()["data"]["body_text"]
    )
    res = await client.delete(EDITOR, headers=auth_headers, params=WHATSAPP)
    assert res.status_code == 204, res.text
    second = await enqueue()
    await NotificationGateway.dispatch_outbox(db_session)
    assert first.body_text == "Hola Alex Example"
    assert second.status == "awaiting_manual" and second.body_text == "Default Alex Example"


async def test_editor_respects_template_permissions(
    client, auth_headers, db_session, test_clinic, monkeypatch
):
    async def read_only(db, clinic_id, role, permission):  # noqa: ARG001
        return permission == "notifications.templates.read"

    monkeypatch.setattr("app.core.auth.dependencies.has_permission_for", read_only)
    assert (await client.get(EDITOR, headers=auth_headers, params=EMAIL)).status_code == 200
    preview = await client.post(f"{EDITOR}/preview", headers=auth_headers, params=EMAIL, json={})
    assert preview.status_code == 200
    assert (
        await client.put(EDITOR, headers=auth_headers, params=EMAIL, json=COPY)
    ).status_code == 403
    assert (await client.delete(EDITOR, headers=auth_headers, params=EMAIL)).status_code == 403

    await db_session.execute(
        update(ClinicMembership)
        .where(ClinicMembership.clinic_id == test_clinic.id)
        .values(role="receptionist")
    )

    async def no_access(*_args):
        return False

    monkeypatch.setattr("app.core.auth.dependencies.has_permission_for", no_access)
    assert (await client.get(EDITOR, headers=auth_headers, params=EMAIL)).status_code == 403


async def test_editor_disallows_edits_on_literal_or_provider_channels(
    client, auth_headers, test_clinic
):
    for channel in ("whatsapp", "sms", "push"):
        params = {**EMAIL, "channel": channel}
        result = await client.get(EDITOR, headers=auth_headers, params=params)
        assert result.json()["data"]["editable"] is False
        assert result.json()["data"]["variables"] == []
        assert (
            await client.put(EDITOR, headers=auth_headers, params=params, json=COPY)
        ).status_code == 409


async def test_legacy_create_checks_the_full_key_including_inactive_rows(
    client, auth_headers, test_clinic
):
    path = "/api/v1/notifications/templates"
    data = {"template_key": KEY, "locale": "es", "body_text": "Example", "is_active": False}
    for channel in ("email", "whatsapp"):
        result = await client.post(path, headers=auth_headers, json={**data, "channel": channel})
        assert result.status_code == 201, result.text
    result = await client.post(path, headers=auth_headers, json={**data, "channel": "whatsapp"})
    assert result.status_code == 409


def test_every_notification_type_has_a_synthetic_context():
    for key in NOTIFICATION_TYPES:
        sample = example_context(key, "es", None)
        assert set(sample) == set(available_fields(key, Channel.EMAIL))
        assert set(available_fields(key, Channel.WHATSAPP)) <= sample.keys()


async def test_default_is_editable_and_saves_without_an_implicit_override(
    client, auth_headers, db_session, test_clinic
):
    res = await client.get(EDITOR, headers=auth_headers, params=EMAIL)
    assert res.status_code == 200
    data = res.json()["data"]
    assert not data["has_override"]
    assert "{{ clinic_name }}" in data["current"]["subject"]
    assert "{{ patient_name }}" in data["current"]["body_html"]
    assert (
        await NotificationService.get_clinic_template(
            db_session, test_clinic.id, KEY, "es", "email"
        )
        is None
    )
    res = await client.put(EDITOR, headers=auth_headers, params=EMAIL, json=data["current"])
    assert res.status_code == 204, res.text


async def test_custom_email_layout_and_legacy_document(
    client, auth_headers, test_clinic, monkeypatch
):
    from uuid import uuid4

    from app.core.email.providers.base import EmailResult, EmailStatus
    from app.modules.notifications.channels import OutboundMessage
    from app.modules.notifications.channels.email_adapter import EmailAdapter

    messages = []

    async def capture(message, db=None, clinic_id=None):
        messages.append(message)
        return EmailResult(status=EmailStatus.SUCCESS, provider="test")

    monkeypatch.setattr(email_service, "send", capture)
    content = {**COPY, "body_html": "<p>Unique content for {{ patient_name }}</p>"}
    preview = await client.post(
        f"{EDITOR}/preview", headers=auth_headers, params=EMAIL, json={"content": content}
    )
    assert preview.status_code == 200, preview.text
    html = preview.json()["data"]["body_html"]
    assert 'class="email-header"' in html and 'class="email-footer"' in html
    assert html.count("Unique content for Alex Example") == 1
    context = example_context(KEY, "es", test_clinic)
    await EmailAdapter().send(
        None,
        OutboundMessage(
            channel=Channel.EMAIL,
            to_address="test@example.invalid",
            clinic_id=uuid4(),
            template_key=KEY,
            locale="es",
            context=context,
            subject=content["subject"],
            body_html=content["body_html"],
        ),
    )
    assert messages[-1].body_html == html
    legacy = "<!DOCTYPE html><html><body><p>Legacy {{ patient_name }}</p></body></html>"
    await EmailAdapter().send(
        None,
        OutboundMessage(
            channel=Channel.EMAIL,
            to_address="test@example.invalid",
            clinic_id=uuid4(),
            template_key=KEY,
            locale="es",
            context=context,
            subject="Legacy",
            body_html=legacy,
        ),
    )
    assert (
        messages[-1].body_html
        == "<!DOCTYPE html><html><body><p>Legacy Alex Example</p></body></html>"
    )


async def test_default_subject_preview_matches_delivery(client, auth_headers, test_clinic):
    res = await client.post(f"{EDITOR}/preview", headers=auth_headers, params=EMAIL, json={})
    assert res.status_code == 200
    assert res.json()["data"]["subject"] == email_service.render_default_subject(
        KEY, "es", example_context(KEY, "es", test_clinic)
    )


async def test_all_shipped_email_defaults_can_be_saved(client, auth_headers, test_clinic):
    from app.core.email.service import TEMPLATES_DIR
    from app.modules.notifications.models import NOTIFICATION_TYPES

    for key in NOTIFICATION_TYPES:
        for folder in sorted(TEMPLATES_DIR.iterdir()):
            if not (folder / f"{key}.html").is_file():
                continue
            path = f"/api/v1/notifications/templates/editor/{key}"
            params = {"channel": "email", "locale": folder.name}
            res = await client.get(path, headers=auth_headers, params=params)
            assert res.status_code == 200, (key, folder.name, res.text)
            content = res.json()["data"]["current"]
            res = await client.put(path, headers=auth_headers, params=params, json=content)
            assert res.status_code == 204, (key, folder.name, res.text)
