"""A message in a dispatch batch is never sent twice by concurrent ticks."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    SendStatus,
    channel_registry,
)
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import CommunicationMessage


def _queued(clinic_id, to_address: str, created_at: datetime) -> CommunicationMessage:
    return CommunicationMessage(
        clinic_id=clinic_id,
        channel=Channel.SMS.value,
        to_address=to_address,
        template_key="manual",
        message_kind="session",
        body_text="Hello",
        status="queued",
        created_at=created_at,
        next_attempt_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_second_tick_does_not_resend_rows_of_a_running_batch(db_session, test_clinic):
    """Committing for the first row releases the batch lock on the others.

    While tick A is busy sending the first message, tick B (another session)
    picks up and sends the second one. A then reaches the second row from its
    stale batch and must skip it instead of sending it again.
    """
    first = _queued(test_clinic.id, "+34600000001", datetime(2026, 1, 1, tzinfo=UTC))
    second = _queued(test_clinic.id, "+34600000002", datetime(2026, 1, 2, tzinfo=UTC))
    db_session.add_all([first, second])
    await db_session.commit()

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    other_tick = async_sessionmaker(engine, expire_on_commit=False)
    sent: list[str] = []

    class ConcurrentSms:
        channel = Channel.SMS
        adapter_name = "concurrent_sms_test"
        raced = False

        async def supports(self, db, clinic_id):  # noqa: ARG002
            return True

        async def send(self, db, msg):  # noqa: ARG002
            sent.append(msg.to_address)
            if not self.raced:
                self.raced = True
                async with other_tick() as session:
                    assert await NotificationGateway.dispatch_outbox(session) == 1
            return AdapterResult(
                status=SendStatus.SENT, provider="fake_sms", provider_message_id="sms.x"
            )

    channel_registry.register(ConcurrentSms())
    try:
        await NotificationGateway.dispatch_outbox(db_session)
    finally:
        channel_registry.unregister("concurrent_sms_test")
        await engine.dispose()

    assert sorted(sent) == ["+34600000001", "+34600000002"]
    await db_session.refresh(first)
    await db_session.refresh(second)
    assert (first.status, second.status) == ("sent", "sent")
