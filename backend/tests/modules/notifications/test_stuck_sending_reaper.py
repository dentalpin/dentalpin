"""A message left in ``sending`` by an interrupted send is retried (#1280).

``_dispatch_one`` commits ``sending`` before the adapter call. A restart in
that window left the row ``sending`` for good: the outbox only reads
``queued``/``failed`` rows, so the message was never sent nor shown as failed.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    SendStatus,
    channel_registry,
)
from app.modules.notifications.gateway import STALE_SENDING_AFTER, NotificationGateway
from app.modules.notifications.models import CommunicationMessage


def _sending(clinic_id, to_address: str, since: datetime, attempts: int = 1):
    return CommunicationMessage(
        clinic_id=clinic_id,
        channel=Channel.SMS.value,
        to_address=to_address,
        template_key="manual",
        message_kind="session",
        body_text="Hello",
        status="sending",
        attempts=attempts,
        max_attempts=5,
        next_attempt_at=since,
        updated_at=since,
    )


@pytest.mark.asyncio
async def test_stale_sending_row_is_retried_fresh_one_is_left_alone(db_session, test_clinic):
    now = datetime.now(UTC)
    stale = now - STALE_SENDING_AFTER - timedelta(minutes=1)
    stuck = _sending(test_clinic.id, "+34600000001", stale)
    in_flight = _sending(test_clinic.id, "+34600000002", now - timedelta(minutes=1))
    spent = _sending(test_clinic.id, "+34600000003", stale, attempts=5)
    db_session.add_all([stuck, in_flight, spent])
    await db_session.commit()

    sent: list[str] = []

    class FakeSms:
        channel = Channel.SMS
        adapter_name = "stuck_sending_test_sms"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            sent.append(msg.to_address)
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_sms", provider_message_id="sms.x"
            )

    channel_registry.register(FakeSms())
    try:
        assert await NotificationGateway.reap_stuck_sending(db_session) == 2
        await NotificationGateway.dispatch_outbox(db_session)
    finally:
        channel_registry.unregister("stuck_sending_test_sms")

    for row in (stuck, in_flight, spent):
        await db_session.refresh(row)

    # The interrupted attempt counts: the retry is the second.
    assert sent == ["+34600000001"]
    assert (stuck.status, stuck.attempts) == ("sent", 2)
    # A send still within the timeout may be in flight: never touched.
    assert (in_flight.status, in_flight.attempts) == ("sending", 1)
    # max_attempts already spent: failed for good, not retried.
    assert (spent.status, spent.attempts, spent.next_attempt_at) == ("failed", 5, None)
    assert spent.error_message == "interrupted while sending (restart or crash)"


@pytest.mark.asyncio
async def test_sending_row_older_than_the_retry_cap_is_failed_not_sent(db_session, test_clinic):
    """A row stuck for days (e.g. from before the reaper existed) is never sent.

    A reminder stuck since before its appointment must not go out afterwards.
    """
    stuck = _sending(test_clinic.id, "+34600000009", datetime.now(UTC) - timedelta(days=2))
    db_session.add(stuck)
    await db_session.commit()

    sent: list[str] = []

    class FakeSms:
        channel = Channel.SMS
        adapter_name = "stuck_sending_old_test_sms"

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            sent.append(msg.to_address)
            return AdapterResult(status=SendStatus.SENT, provider="fake_sms")

    channel_registry.register(FakeSms())
    try:
        assert await NotificationGateway.reap_stuck_sending(db_session) == 1
        await NotificationGateway.dispatch_outbox(db_session)
    finally:
        channel_registry.unregister("stuck_sending_old_test_sms")

    await db_session.refresh(stuck)
    assert sent == []
    assert (stuck.status, stuck.attempts, stuck.next_attempt_at) == ("failed", 1, None)
    assert stuck.error_message == "interrupted while sending; too old to retry"
