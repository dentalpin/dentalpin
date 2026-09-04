"""Tests for the multi-channel notification gateway + channel adapters."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    ChannelAdapter,
    SendStatus,
    channel_registry,
)
from app.modules.notifications.channels.email_adapter import EmailAdapter
from app.modules.notifications.gateway import NotificationGateway, _backoff_seconds
from app.modules.notifications.models import (
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.notifications.service import NotificationService


@pytest_asyncio.fixture
async def whatsapp_adapter():
    """A fake WhatsApp adapter that always sends, registered for the test."""

    class FakeWhatsApp:
        channel = Channel.WHATSAPP
        adapter_name = "fake_whatsapp_test"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_whatsapp", provider_message_id="wamid.x"
            )

    adapter = FakeWhatsApp()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("fake_whatsapp_test")


async def _email_template(db: AsyncSession, clinic_id, key: str = "appointment_confirmation"):
    tmpl = NotificationTemplate(
        clinic_id=clinic_id,
        channel="email",
        template_key=key,
        locale="es",
        subject="Hola",
        body_html="<p>{{patient_name}}</p>",
        is_system=False,
    )
    db.add(tmpl)
    await db.commit()
    return tmpl


async def _approved_hsm(db: AsyncSession, clinic_id, key: str = "appointment_confirmation"):
    """An approved WhatsApp HSM mapping so proactive WhatsApp is viable."""
    tmpl = NotificationTemplate(
        clinic_id=clinic_id,
        channel="whatsapp",
        template_key=key,
        locale="es",
        provider_template_name="hsm_test",
        provider_template_status="approved",
        is_system=False,
    )
    db.add(tmpl)
    await db.commit()
    return tmpl


async def _channel_settings(
    db: AsyncSession, clinic_id, preferred: str = "whatsapp", fallback: bool = True
):
    settings = await NotificationService.get_or_create_clinic_settings(db, clinic_id)
    settings.preferred_channel = preferred
    settings.fallback_enabled = fallback
    settings.manual_channels = [preferred]
    await db.commit()
    return settings


# --------------------------------------------------------------------------- #
# Adapter contract + registry
# --------------------------------------------------------------------------- #
def test_email_adapter_satisfies_protocol():
    adapter = EmailAdapter()
    assert isinstance(adapter, ChannelAdapter)
    assert adapter.channel == Channel.EMAIL
    assert channel_registry.get_for_channel(Channel.EMAIL) is not None


def test_registry_register_is_idempotent_and_unregisterable():
    class FakeAdapter:
        channel = Channel.WHATSAPP
        adapter_name = "fake_test_adapter"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(status=SendStatus.SENT, provider="fake")

    a = FakeAdapter()
    channel_registry.register(a)
    channel_registry.register(a)  # idempotent — no duplicate, no raise
    # last registered for the channel wins
    assert channel_registry.get_for_channel(Channel.WHATSAPP) is a
    assert channel_registry.get_by_name("fake_test_adapter") is a
    channel_registry.unregister("fake_test_adapter")
    # by_name is gone; get_for_channel may still resolve another adapter
    # (e.g. whatsapp_kapso's, registered process-wide at import).
    assert channel_registry.get_by_name("fake_test_adapter") is None


def test_backoff_is_exponential_and_capped():
    assert _backoff_seconds(1) == 60
    assert _backoff_seconds(2) == 120
    assert _backoff_seconds(3) == 240
    assert _backoff_seconds(99) == 3600  # capped at 1h


# --------------------------------------------------------------------------- #
# Enqueue + dispatch (email round-trip through the console provider)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_enqueue_then_dispatch_sends_email(db_session, test_patient):
    await _email_template(db_session, test_patient.clinic_id)

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        to_address=test_patient.email,
    )
    assert msg is not None
    assert msg.status == "queued"
    assert msg.channel == "email"
    assert msg.to_address == test_patient.email

    attempted = await NotificationGateway.dispatch_outbox(db_session)
    assert attempted == 1
    await db_session.refresh(msg)
    assert msg.status == "sent"
    assert msg.sent_at is not None
    assert msg.attempts == 1


@pytest.mark.asyncio
async def test_dedup_key_is_idempotent(db_session, test_patient):
    await _email_template(db_session, test_patient.clinic_id)
    key = f"appointment_reminder:{uuid4()}"
    first = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        to_address=test_patient.email,
        dedup_key=key,
    )
    second = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        to_address=test_patient.email,
        dedup_key=key,
    )
    assert first is not None
    assert second is None  # idempotent no-op


# --------------------------------------------------------------------------- #
# Consent
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_do_not_contact_hard_blocks_even_force(db_session, test_patient):
    test_patient.do_not_contact = True
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        to_address=test_patient.email,
        force_send=True,
    )
    assert msg is not None
    assert msg.status == "skipped"
    assert msg.error_message == "do_not_contact"


@pytest.mark.asyncio
async def test_email_opt_out_skips(db_session, test_patient):
    from app.modules.notifications.models import NotificationPreference

    db_session.add(
        NotificationPreference(
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            email_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        to_address=test_patient.email,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "patient_opted_out"


# --------------------------------------------------------------------------- #
# Retry / backoff with a failing adapter
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def failing_email_adapter():
    """Override the email channel with an adapter that always fails."""

    class FailingEmail:
        channel = Channel.EMAIL
        adapter_name = "failing_email_test"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(status=SendStatus.FAILED, provider="failing", error_message="boom")

    adapter = FailingEmail()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("failing_email_test")


@pytest.mark.asyncio
async def test_failed_send_schedules_backoff(db_session, test_patient, failing_email_adapter):
    await _email_template(db_session, test_patient.clinic_id)
    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        to_address=test_patient.email,
    )

    await NotificationGateway.dispatch_outbox(db_session)
    await db_session.refresh(msg)
    assert msg.status == "failed"
    assert msg.attempts == 1
    assert msg.error_message == "boom"
    assert msg.next_attempt_at is not None and msg.next_attempt_at > datetime.now(UTC)

    # A second tick before next_attempt_at must not re-pick the row.
    attempted = await NotificationGateway.dispatch_outbox(db_session)
    assert attempted == 0


# --------------------------------------------------------------------------- #
# Agent tool wrapper
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_send_notification_tool_enqueues(db_session, test_patient):
    from types import SimpleNamespace

    from app.modules.notifications.tools import SendNotificationArgs, _send_notification

    await _email_template(db_session, test_patient.clinic_id)
    ctx = SimpleNamespace(db=db_session, clinic_id=test_patient.clinic_id, supervisor_id=None)
    result = await _send_notification(
        ctx,
        SendNotificationArgs(
            patient_id=test_patient.id, notification_type="appointment_confirmation"
        ),
    )
    assert result["status"] == "queued"
    assert result["channel"] == "email"

    row = (
        await db_session.execute(
            select(CommunicationMessage).where(CommunicationMessage.id == result["message_id"])
        )
    ).scalar_one()
    # tool auto-injected patient_name into context
    assert row.context_data.get("patient_name") == "Test Patient"


# --------------------------------------------------------------------------- #
# 2A — inbound replies + 24h session window
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_record_inbound_reply_opens_window_and_dedups(db_session, test_patient):
    first = await NotificationGateway.record_inbound_reply(
        db_session,
        test_patient.clinic_id,
        channel="whatsapp",
        from_address=test_patient.phone,
        body="Hola, confirmo",
        patient_id=test_patient.id,
        provider_message_id="wamid.inbound.1",
    )
    assert first is not None
    assert first.direction == "inbound"
    assert first.status == "received"
    assert first.body_text == "Hola, confirmo"

    # window is now open
    from app.modules.notifications.service import NotificationService

    prefs = await NotificationService.get_patient_preferences(
        db_session, test_patient.clinic_id, test_patient.id
    )
    assert prefs.last_inbound_at is not None

    # same provider_message_id is idempotent
    dup = await NotificationGateway.record_inbound_reply(
        db_session,
        test_patient.clinic_id,
        channel="whatsapp",
        from_address=test_patient.phone,
        body="dup",
        patient_id=test_patient.id,
        provider_message_id="wamid.inbound.1",
    )
    assert dup is None


@pytest.mark.asyncio
async def test_reply_within_window_enqueues_session(db_session, test_patient, whatsapp_adapter):
    # open the window
    await NotificationGateway.record_inbound_reply(
        db_session,
        test_patient.clinic_id,
        channel="whatsapp",
        from_address=test_patient.phone,
        body="hola",
        patient_id=test_patient.id,
        provider_message_id="wamid.in.2",
    )
    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "reply",
        context={},
        patient_id=test_patient.id,
        channels=["whatsapp"],
        message_kind="session",
        body_text="Le confirmo su cita",
        force_send=True,
    )
    assert msg is not None
    assert msg.status == "queued"
    assert msg.channel == "whatsapp"
    assert msg.message_kind == "session"
    assert msg.body_text == "Le confirmo su cita"


@pytest.mark.asyncio
async def test_reply_outside_window_is_blocked(db_session, test_patient, whatsapp_adapter):
    # window closed: last_inbound_at 25h ago
    db_session.add(
        NotificationPreference(
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            last_inbound_at=datetime.now(UTC) - timedelta(hours=25),
        )
    )
    await db_session.commit()
    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "reply",
        context={},
        patient_id=test_patient.id,
        channels=["whatsapp"],
        message_kind="session",
        body_text="tarde",
        force_send=True,
    )
    assert msg.status == "skipped"


# --------------------------------------------------------------------------- #
# #287 — clinic preferred channel + fallback ordering
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_clinic_channels_missing_settings_row_is_email_only(db_session, test_clinic):
    """Ponytail: a clinic without a settings row stays email-only."""
    order = await NotificationGateway._clinic_channels(db_session, test_clinic.id)
    assert order == ["email"]


@pytest.mark.asyncio
async def test_clinic_channels_preferred_whatsapp_appends_email_fallback(
    db_session, test_clinic, whatsapp_adapter
):
    await _channel_settings(db_session, test_clinic.id, preferred="whatsapp", fallback=True)
    order = await NotificationGateway._clinic_channels(db_session, test_clinic.id)
    assert order == ["whatsapp", "email"]


@pytest.mark.asyncio
async def test_clinic_channels_no_fallback_is_preferred_only(
    db_session, test_clinic, whatsapp_adapter
):
    await _channel_settings(db_session, test_clinic.id, preferred="whatsapp", fallback=False)
    order = await NotificationGateway._clinic_channels(db_session, test_clinic.id)
    assert order == ["whatsapp"]


@pytest.mark.asyncio
async def test_clinic_channels_fallback_skips_unavailable_whatsapp(db_session, test_clinic):
    """Preferred email + fallback on, but no connected WhatsApp adapter:
    the order must not advertise a channel the clinic cannot use."""
    await _channel_settings(db_session, test_clinic.id, preferred="email", fallback=True)
    order = await NotificationGateway._clinic_channels(db_session, test_clinic.id)
    assert order == ["email"]


# --------------------------------------------------------------------------- #
# #287 bug 11 — missing prefs row must not block proactive WhatsApp
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_missing_prefs_row_does_not_block_whatsapp(
    db_session, test_patient, whatsapp_adapter
):
    """No NotificationPreference row exists: WhatsApp is opt-out like email,
    so a preferred-WhatsApp auto-send still resolves to WhatsApp."""
    await _channel_settings(db_session, test_patient.clinic_id, preferred="whatsapp")
    await _approved_hsm(db_session, test_patient.clinic_id)

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
    )
    assert msg is not None
    assert msg.status == "queued"
    assert msg.channel == "whatsapp"
    assert msg.to_address == test_patient.phone


@pytest.mark.asyncio
async def test_explicit_whatsapp_opt_out_falls_back_to_email(
    db_session, test_patient, whatsapp_adapter
):
    """An explicit whatsapp_enabled=False still blocks proactive WhatsApp;
    with fallback enabled the send lands on email instead."""
    await _channel_settings(db_session, test_patient.clinic_id, preferred="whatsapp")
    await _approved_hsm(db_session, test_patient.clinic_id)
    db_session.add(
        NotificationPreference(
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            whatsapp_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
    )
    assert msg.status == "queued"
    assert msg.channel == "email"
    assert msg.to_address == test_patient.email


@pytest.mark.asyncio
async def test_skip_row_carries_preferred_channel_not_email(
    db_session, test_patient, whatsapp_adapter
):
    """Opt-out + fallback off ⇒ nothing viable. The skip row must be labeled
    with the clinic's preferred channel, not a hardcoded 'email'."""
    await _channel_settings(
        db_session, test_patient.clinic_id, preferred="whatsapp", fallback=False
    )
    await _approved_hsm(db_session, test_patient.clinic_id)
    db_session.add(
        NotificationPreference(
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            whatsapp_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "no_viable_channel"
    assert msg.channel == "whatsapp"


@pytest.mark.asyncio
async def test_force_send_whatsapp_needs_no_opt_in_but_still_needs_hsm(
    db_session, test_patient, whatsapp_adapter
):
    """A manual (force) WhatsApp send works without a prefs opt-in row, but
    proactive WhatsApp still requires an approved HSM — no direct-text
    fallback, ever."""
    await _channel_settings(db_session, test_patient.clinic_id, preferred="whatsapp")

    # No HSM mapped: not viable, even forced — the send is skipped.
    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        channels=["whatsapp"],
        force_send=True,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "no_viable_channel"

    # With an approved HSM the same forced send queues on WhatsApp.
    await _approved_hsm(db_session, test_patient.clinic_id)
    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        channels=["whatsapp"],
        force_send=True,
    )
    assert msg.status == "queued"
    assert msg.channel == "whatsapp"
    assert msg.to_address == test_patient.phone


@pytest.mark.asyncio
async def test_explicit_whatsapp_opt_out_blocks_even_force_send(
    db_session, test_patient, whatsapp_adapter
):
    """A recorded whatsapp_enabled=False blocks force sends too — the
    reminder cron and the staff Send buttons both pass force_send, and
    neither may override an explicit opt-out (same contract as
    email_enabled)."""
    await _channel_settings(db_session, test_patient.clinic_id, preferred="whatsapp")
    await _approved_hsm(db_session, test_patient.clinic_id)
    db_session.add(
        NotificationPreference(
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            whatsapp_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        test_patient.clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=test_patient.id,
        channels=["whatsapp"],
        force_send=True,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "no_viable_channel"


# --------------------------------------------------------------------------- #
# #231 PR1 - SMS channel core support
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def sms_adapter():
    """A fake SMS adapter that always sends, registered for the test."""

    class FakeSms:
        channel = Channel.SMS
        adapter_name = "fake_sms_test"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_sms", provider_message_id="sms.x"
            )

    adapter = FakeSms()
    channel_registry.register(adapter)
    yield adapter
    channel_registry.unregister("fake_sms_test")


@pytest.mark.asyncio
async def test_sms_resolves_with_explicit_channel(db_session, test_patient, sms_adapter):
    """SMS rides patients.phone; text-only, no template approval needed."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_phone = test_patient.phone
    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
    )
    assert msg is not None
    assert msg.status == "queued"
    assert msg.channel == "sms"
    assert msg.to_address == patient_phone


@pytest.mark.asyncio
async def test_sms_template_and_session_kinds_resolve(db_session, test_patient, sms_adapter):
    """SMS works as both template and session sends (no Meta-style gate)."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    for kind in ("template", "session"):
        msg = await NotificationGateway.enqueue(
            db_session,
            clinic_id,
            "appointment_confirmation",
            context={},
            patient_id=patient_id,
            channels=["sms"],
            message_kind=kind,
            body_text="hola" if kind == "session" else None,
        )
        assert msg.status == "queued"
        assert msg.channel == "sms"
        assert msg.message_kind == kind


@pytest.mark.asyncio
async def test_explicit_sms_opt_out_blocks_even_force_send(db_session, test_patient, sms_adapter):
    """sms_enabled=False blocks SMS exactly like the whatsapp opt-out."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    db_session.add(
        NotificationPreference(
            clinic_id=clinic_id,
            patient_id=patient_id,
            sms_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
        force_send=True,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "no_viable_channel"


@pytest.mark.asyncio
async def test_sms_opt_out_falls_back_to_email(db_session, test_patient, sms_adapter):
    """Opted-out SMS with fallback enabled lands on email instead."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_email = test_patient.email
    await _channel_settings(db_session, clinic_id, preferred="sms")
    db_session.add(
        NotificationPreference(
            clinic_id=clinic_id,
            patient_id=patient_id,
            sms_enabled=False,
        )
    )
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
    )
    assert msg.status == "queued"
    assert msg.channel == "email"
    assert msg.to_address == patient_email


@pytest.mark.asyncio
async def test_do_not_contact_blocks_sms(db_session, test_patient, sms_adapter):
    """do_not_contact is a hard block on SMS like every other channel."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    test_patient.do_not_contact = True
    await db_session.commit()

    msg = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
        force_send=True,
    )
    assert msg.status == "skipped"
    assert msg.error_message == "do_not_contact"


@pytest.mark.asyncio
async def test_clinic_channels_sms_fallback_order(
    db_session, test_clinic, sms_adapter, whatsapp_adapter
):
    """Preferred SMS + fallback: connected channels follow in enum order."""
    clinic_id = test_clinic.id
    await _channel_settings(db_session, clinic_id, preferred="sms", fallback=True)
    order = await NotificationGateway._clinic_channels(db_session, clinic_id)
    assert order == ["sms", "email", "whatsapp"]


@pytest.mark.asyncio
async def test_sms_rate_limit_skips_when_exhausted(db_session, test_patient, sms_adapter):
    """Second SMS of a 1/day clinic is skipped, not queued."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    settings = await NotificationService.get_or_create_clinic_settings(db_session, clinic_id)
    settings.sms_daily_limit = 1
    await db_session.commit()

    first = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_confirmation",
        context={},
        patient_id=patient_id,
        channels=["sms"],
    )
    assert first.status == "queued"

    second = await NotificationGateway.enqueue(
        db_session,
        clinic_id,
        "appointment_reminder",
        context={},
        patient_id=patient_id,
        channels=["sms"],
    )
    assert second.status == "skipped"
    assert second.error_message == "sms_rate_limited"
