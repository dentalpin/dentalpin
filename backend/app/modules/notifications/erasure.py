"""GDPR erasure contributor for the notifications module (#546).

Owns the ``notifications`` coverage scope: redacts this module's own
copies of the erased contacts from the communication log and reports its
own :class:`~app.core.erasure.types.ErasureCoverage`. Registered via
``NotificationsModule.get_erasure_contributors``; pulled by ``gdpr``
inside the erasure transaction (ADR 0038).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erasure.types import ErasureContributor, ErasureCoverage

from .models import CommunicationMessage

#: Outbound channels whose recipient address is a copy of a patient contact
#: field, mapped to the GDPR erasure category that blanks it. Only the
#: channels the ``Channel`` enum defines are listed; ``push`` is excluded
#: because its recipient is a device subscription endpoint, not a copy of
#: a patient contact field.
ERASURE_CHANNEL_CATEGORY: dict[str, str] = {
    "email": "email",
    "sms": "phone",
    "whatsapp": "phone",
}

#: Left in place of a redacted recipient so the NOT NULL column still holds a
#: value and the audit reads as deliberately cleared, not merely empty.
ERASED_PLACEHOLDER = "[erased]"


class NotificationsErasureContributor(ErasureContributor):
    """Redact a patient's contact copies from the communication log."""

    @property
    def scope(self) -> str:
        return "notifications"

    async def erase(
        self,
        clinic_id: UUID,
        patient_id: UUID,
        erased: list[str],
        retained: list[str],
        db: AsyncSession,
    ) -> ErasureCoverage:
        """Redact the patient's messages for the erased contact categories.

        Runs inside the erasure's transaction, so the audit log and this
        redaction commit or roll back together. Only rows whose channel
        matches an erased contact category are cleared — the recipient
        address, subject, body, template context and failure text of the
        patient's own messages (a failed send persists the refused address
        in ``error_message``). The row itself stays: the outbox is also the
        send audit, and a completed erasure must be visible without erasing
        the fact that messages were sent. A row still waiting to go out
        (``queued``, ``failed`` or ``awaiting_manual``) is cancelled (``skipped``) so
        a later outbox tick skips it; a ``sending`` row is cancelled too,
        but a send already on the wire still reports its terminal status
        from the dispatcher, whose commit can land after ours and supersede
        the cancel (#546).
        """
        erased_set = set(erased)
        channels = [
            channel
            for channel, category in ERASURE_CHANNEL_CATEGORY.items()
            if category in erased_set
        ]
        if channels:
            rows = (
                (
                    await db.execute(
                        select(CommunicationMessage)
                        .where(
                            CommunicationMessage.clinic_id == clinic_id,
                            CommunicationMessage.patient_id == patient_id,
                            CommunicationMessage.channel.in_(channels),
                            CommunicationMessage.to_address != ERASED_PLACEHOLDER,
                        )
                        .order_by(CommunicationMessage.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                )
                .scalars()
                .all()
            )
            for message in rows:
                message.to_address = ERASED_PLACEHOLDER
                message.subject = None
                message.body_text = None
                message.context_data = None
                message.error_message = None
                if message.status in ("queued", "sending", "failed", "awaiting_manual"):
                    # Never dispatch an erased recipient or an emptied message:
                    # cancel the unsent row so the outbox tick skips it.
                    message.status = "skipped"

        # A contact scope is scrubbed only when a contact category was
        # actually erasable; otherwise it holds what the legal-hold gate
        # kept (retained), or nothing at all (not_applicable).
        status: Literal["erased", "retained", "not_applicable"]
        if {"email", "phone"} & erased_set:
            status = "erased"
        elif {"email", "phone"} & set(retained):
            status = "retained"
        else:
            status = "not_applicable"
        return ErasureCoverage(
            scope=self.scope,
            status=status,
            detail="Recipient, subject, body, template context and failure text on the communication log.",
        )
