"""Exercise the optional delivery hooks without a vendor module."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.database import async_session_maker
from app.modules.notifications.channels import AdapterResult, Channel, SendStatus, channel_registry
from app.modules.notifications.erasure import (
    ERASED_PLACEHOLDER,
    NotificationsErasureContributor,
)
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import (
    ClinicChannelSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.notifications.service import NotificationService

RENDERED = "Synthetic appointment reminder"
NORMALIZED_MOBILE = "+12025550101"


class StubAdapter:
    channel = Channel.WHATSAPP
    requires_provider_template = False

    def __init__(self, name: str) -> None:
        self.adapter_name = name
        self.supports = AsyncMock(return_value=True)
        self.send = AsyncMock(
            return_value=AdapterResult(SendStatus.DEFERRED, name, body_text=RENDERED)
        )


@pytest.fixture
def adapters():
    first, alternate = StubAdapter("stub_hooks_first"), StubAdapter("stub_hooks_alternate")
    for adapter in (first, alternate):
        channel_registry.register(adapter)
    try:
        yield first, alternate
    finally:
        for adapter in (first, alternate):
            channel_registry.unregister(adapter.adapter_name)


@pytest.fixture
async def selected_adapter(db_session, test_clinic, adapters):
    first, _ = adapters
    selection = ClinicChannelSettings(
        clinic_id=test_clinic.id,
        channel=Channel.WHATSAPP,
        adapter_name=first.adapter_name,
    )
    db_session.add(selection)
    await db_session.flush()
    return selection


async def _enqueue(db, patient, **options):
    return await NotificationGateway.enqueue(
        db,
        patient.clinic_id,
        "appointment_reminder",
        context=options.pop("context", {"patient_name": "Alex Example"}),
        patient_id=patient.id,
        force_send=True,
        **options,
    )


async def _opt_in(db, patient):
    prefs = NotificationPreference(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        whatsapp_opt_in_at=datetime.now(UTC),
        last_inbound_at=datetime.now(UTC),
    )
    db.add(prefs)
    await db.flush()
    return prefs


@pytest.mark.asyncio
async def test_recipient_normalization_controls_fallback_and_deferred_body(
    db_session, test_patient, adapters, selected_adapter
):
    first, _ = adapters
    first.normalize_recipient = AsyncMock(side_effect=[None, NORMALIZED_MOBILE])

    fallback = await _enqueue(db_session, test_patient, channels=["whatsapp", "email"])
    assert fallback.channel == "email"
    fallback.status = "skipped"
    await db_session.flush()

    draft = await _enqueue(db_session, test_patient, channels=["whatsapp"], body_text="Original")
    assert draft.to_address == NORMALIZED_MOBILE
    assert draft.body_text == "Original"
    assert first.normalize_recipient.await_count == 2

    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert (draft.status, draft.body_text, draft.sent_at) == ("awaiting_manual", RENDERED, None)
    outbound = first.send.await_args.args[1]
    assert outbound.to_address == NORMALIZED_MOBILE
    assert outbound.metadata["literal_body"] is True


@pytest.mark.asyncio
async def test_consent_required_at_enqueue_and_again_before_dispatch(
    db_session, test_patient, adapters, selected_adapter
):
    first, _ = adapters
    first.requires_whatsapp_opt_in = True

    blocked = await _enqueue(db_session, test_patient, channels=["whatsapp"])
    assert blocked.status == "skipped"
    prefs = await _opt_in(db_session, test_patient)
    queued = await _enqueue(db_session, test_patient, channels=["whatsapp"])
    assert queued.status == "queued"

    prefs.whatsapp_opt_in_at = None
    await db_session.flush()
    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert queued.status == "skipped"
    assert queued.error_message == "whatsapp_consent_required"
    first.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_follows_the_clinics_current_adapter(
    db_session, test_patient, adapters, selected_adapter
):
    first, alternate = adapters
    first.requires_whatsapp_opt_in = True
    await _opt_in(db_session, test_patient)
    queued = await _enqueue(db_session, test_patient, channels=["whatsapp"])
    assert queued.provider is None

    selected_adapter.adapter_name = alternate.adapter_name
    await db_session.flush()

    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert queued.status == "awaiting_manual"
    assert queued.provider == alternate.adapter_name
    first.send.assert_not_awaited()
    alternate.send.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("uses_provider_template", [True, False])
async def test_appointment_timestamp_is_kept_for_manual_delivery_only(
    db_session, test_patient, adapters, selected_adapter, uses_provider_template
):
    first, _ = adapters
    first.requires_provider_template = uses_provider_template
    db_session.add(
        NotificationTemplate(
            clinic_id=test_patient.clinic_id,
            template_key="appointment_reminder",
            channel="whatsapp",
            locale="es",
            subject="Reminder",
            body_text="Template copy",
            provider_template_name="approved_reminder",
            provider_template_status="approved",
            is_system=False,
        )
    )
    timestamp = "2026-11-20T09:00:00+01:00"
    draft = await _enqueue(
        db_session, test_patient, channels=["whatsapp"], body_text="Literal copy",
        context={"patient_name": "Alex Example", "appointment_start_at": timestamp},
    )

    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    outbound = first.send.await_args.args[1]
    assert draft.context_data["appointment_start_at"] == timestamp
    assert outbound.context["patient_name"] == "Alex Example"
    if uses_provider_template:
        assert "appointment_start_at" not in outbound.context
        assert outbound.body_text == "Template copy"
        assert outbound.metadata["literal_body"] is False
    else:
        assert outbound.context["appointment_start_at"] == timestamp
        assert outbound.body_text == "Literal copy"
        assert outbound.metadata["literal_body"] is True


@pytest.mark.asyncio
async def test_session_availability_and_replies_follow_the_selected_adapter(
    client, db_session, auth_headers, test_patient, adapters, selected_adapter
):
    first, alternate = adapters
    first.supports_session_replies = False
    await _opt_in(db_session, test_patient)

    async def session_available():
        response = await client.get("/api/v1/notifications/channels", headers=auth_headers)
        assert response.status_code == 200
        available = response.json()["data"]
        assert "whatsapp" in available["available"]
        return available["whatsapp_session_available"]

    assert await session_available() is False
    reply_path = f"/api/v1/notifications/conversations/{test_patient.id}/reply"
    response = await client.post(reply_path, json={"body": "Reply"}, headers=auth_headers)
    assert response.status_code == 409

    selected_adapter.adapter_name = alternate.adapter_name
    await db_session.flush()
    assert await session_available() is True
    response = await client.post(reply_path, json={"body": "Reply"}, headers=auth_headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_patient_preferences_record_and_clear_affirmative_consent(
    client, auth_headers, test_patient
):
    path = f"/api/v1/notifications/preferences/patient/{test_patient.id}"
    response = await client.get(path, headers=auth_headers)
    assert response.json()["data"]["whatsapp_opt_in_at"] is None

    async def update(**changes):
        response = await client.put(path, json=changes, headers=auth_headers)
        assert response.status_code == 200
        return response.json()["data"]["whatsapp_opt_in_at"]

    first = await update(whatsapp_consent=True)
    assert datetime.fromisoformat(first).utcoffset() is not None
    assert await update(whatsapp_consent=True) == first
    assert await update(whatsapp_enabled=False, whatsapp_consent=True) is None
    assert await update(whatsapp_enabled=True) is None
    assert await update(whatsapp_consent=True)
    assert await update(whatsapp_consent=False) is None


@pytest.mark.asyncio
async def test_patient_preferences_expose_the_selected_adapters_consent_policy(
    client, db_session, auth_headers, test_patient, adapters, selected_adapter
):
    first, alternate = adapters
    first.requires_whatsapp_opt_in = True
    path = f"/api/v1/notifications/preferences/patient/{test_patient.id}"

    response = await client.get(path, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["whatsapp_consent_required"] is True

    selected_adapter.adapter_name = alternate.adapter_name
    await db_session.flush()
    response = await client.get(path, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["whatsapp_consent_required"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("block", ["whatsapp_consent", "whatsapp_enabled", "do_not_contact"])
async def test_revoking_contact_cancels_pending_whatsapp_only(
    client, db_session, auth_headers, test_patient, block
):
    def message(channel, status):
        return CommunicationMessage(
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            channel=channel,
            direction="outbound",
            to_address=NORMALIZED_MOBILE,
            template_key="appointment_reminder",
            status=status,
        )

    draft, email, sent = (
        message("whatsapp", "awaiting_manual"),
        message("email", "awaiting_manual"),
        message("whatsapp", "sent"),
    )
    db_session.add_all([draft, email, sent])
    await db_session.flush()
    if block == "do_not_contact":
        path = f"/api/v1/patients/{test_patient.id}"
        value = True
    else:
        path = f"/api/v1/notifications/preferences/patient/{test_patient.id}"
        value = False

    response = await client.put(path, json={block: value}, headers=auth_headers)
    assert response.status_code == 200
    for row in (draft, email, sent):
        await db_session.refresh(row)
    assert [draft.status, email.status, sent.status] == ["skipped", "awaiting_manual", "sent"]


@pytest.mark.asyncio
async def test_deferred_result_does_not_restore_revoked_consent(
    db_session, test_patient, adapters, selected_adapter
):
    first, _ = adapters
    first.requires_whatsapp_opt_in = True
    await _opt_in(db_session, test_patient)
    clinic_id, patient_id = test_patient.clinic_id, test_patient.id
    draft = await _enqueue(db_session, test_patient, channels=["whatsapp"])

    async def revoke_while_sending(db, outbound):
        async with async_session_maker() as revoke_db:
            await NotificationService.update_patient_preferences(
                revoke_db, clinic_id, patient_id, {"whatsapp_consent": False}
            )
        return AdapterResult(SendStatus.DEFERRED, first.adapter_name, body_text=RENDERED)

    first.send.side_effect = revoke_while_sending
    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert draft.status == "skipped"
    assert draft.body_text is None


@pytest.mark.asyncio
async def test_inflight_deferred_result_does_not_restore_erased_draft(
    db_session, test_patient, adapters, selected_adapter
):
    first, _ = adapters
    clinic_id, patient_id = test_patient.clinic_id, test_patient.id
    draft = await _enqueue(db_session, test_patient, channels=["whatsapp"], body_text="Draft")

    async def erase_while_sending(db, outbound):
        async with async_session_maker.begin() as erasure_db:
            await NotificationsErasureContributor().erase(
                clinic_id, patient_id, ["phone"], [], erasure_db
            )
        return AdapterResult(SendStatus.DEFERRED, first.adapter_name, body_text=RENDERED)

    first.send.side_effect = erase_while_sending
    assert await NotificationGateway.dispatch_outbox(db_session) == 1
    assert draft.status == "skipped"
    assert draft.to_address == ERASED_PLACEHOLDER
    assert draft.body_text is None
    assert draft.context_data is None


@pytest.mark.asyncio
async def test_erasure_select_locks_the_row_before_the_deferred_adapter_finishes(
    db_session, test_patient, adapters, selected_adapter
):
    first, _ = adapters
    clinic_id, patient_id = test_patient.clinic_id, test_patient.id
    draft = await _enqueue(db_session, test_patient, channels=["whatsapp"], body_text="Draft")
    message_id = draft.id
    sending, adapter_can_return = asyncio.Event(), asyncio.Event()

    async def finish_after_erasure_reads(db, outbound):
        sending.set()
        await adapter_can_return.wait()
        return AdapterResult(SendStatus.DEFERRED, first.adapter_name, body_text=RENDERED)

    first.send.side_effect = finish_after_erasure_reads
    dispatch = asyncio.create_task(NotificationGateway.dispatch_outbox(db_session))
    try:
        await asyncio.wait_for(sending.wait(), timeout=5)
        async with async_session_maker.begin() as erasure_db:
            await NotificationsErasureContributor().erase(
                clinic_id, patient_id, ["phone"], [], erasure_db
            )
            # Erasure has read the row but has not flushed its updates yet.
            async with async_session_maker() as probe:
                unlocked_id = await probe.scalar(
                    select(CommunicationMessage.id)
                    .where(CommunicationMessage.id == message_id)
                    .with_for_update(skip_locked=True)
                )
            assert unlocked_id is None
            adapter_can_return.set()
    finally:
        adapter_can_return.set()
        assert await asyncio.wait_for(dispatch, timeout=5) == 1

    assert draft.status == "skipped"
    assert draft.to_address == ERASED_PLACEHOLDER
    assert draft.body_text is None


@pytest.mark.asyncio
async def test_conversation_exposes_pending_and_staff_declared_status(
    client, db_session, auth_headers, test_patient
):
    for status in ("awaiting_manual", "sent"):
        db_session.add(
            CommunicationMessage(
                clinic_id=test_patient.clinic_id,
                patient_id=test_patient.id,
                channel="whatsapp",
                to_address=NORMALIZED_MOBILE,
                template_key="appointment_reminder",
                status=status,
                context_data={"manual_delivery": {"action": "mark_sent", "user_id": "test-actor"}}
                if status == "sent"
                else {},
            )
        )
    await db_session.flush()
    response = await client.get(
        f"/api/v1/notifications/conversations/{test_patient.id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert {row["status"]: row["sent_manually"] for row in response.json()["data"]} == {
        "awaiting_manual": False,
        "sent": True,
    }
