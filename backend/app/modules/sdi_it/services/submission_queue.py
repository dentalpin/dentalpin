"""PEC worker for ``sdi_it_records`` (ADR 0025 §3, transport ``pec``).

``process_clinic`` sends this clinic's ``pending`` files through its PEC
mailbox, one message per file, then polls the mailbox for SDI receipts
and applies them. Rows are locked ``FOR UPDATE SKIP LOCKED`` and the
session commits *before* each network call, so overlapping ticks never
double-send and no row lock is held across I/O (the nav_online posture).

Transport errors back off ``min(120·2^(attempts-1), 3600)`` seconds per
row; a mailbox-level failure (login, DNS) pauses the whole clinic for ten
minutes and surfaces in ``last_error``. Receipts that name no record are
logged and skipped (the mailbox may hold files from another system).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password

from ..models import SdiItRecord, SdiItSettings
from . import pec_transport
from .invoice_state import sync_invoice_state
from .receipts import ReceiptError, apply_receipt

logger = logging.getLogger(__name__)

_BATCH = 20
MAX_ATTEMPTS = 8


def credentials_for(settings: SdiItSettings) -> pec_transport.PecCredentials | None:
    if not (
        settings.pec_address
        and settings.smtp_host
        and settings.imap_host
        and settings.smtp_username
        and settings.smtp_password_encrypted
    ):
        return None
    return pec_transport.PecCredentials(
        address=settings.pec_address,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port or 465,
        imap_host=settings.imap_host,
        imap_port=settings.imap_port or 993,
        username=settings.smtp_username,
        password=decrypt_password(settings.smtp_password_encrypted),
        imap_folder=settings.imap_folder or "INBOX",
    )


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(120 * (2 ** max(attempts - 1, 0)), 3600))


async def _due_pending(db: AsyncSession, clinic_id: UUID) -> list[SdiItRecord]:
    now = datetime.now(UTC)
    stmt = (
        select(SdiItRecord)
        .where(
            SdiItRecord.clinic_id == clinic_id,
            SdiItRecord.state == "pending",
            (SdiItRecord.next_attempt_at.is_(None)) | (SdiItRecord.next_attempt_at <= now),
        )
        .order_by(SdiItRecord.created_at)
        .limit(_BATCH)
        .with_for_update(skip_locked=True)
    )
    return list((await db.execute(stmt)).scalars().all())


async def process_clinic(db: AsyncSession, clinic_id: UUID) -> dict[str, int]:
    """Send due pending files, then poll for receipts. Returns counters."""
    counters = {"sent": 0, "failed": 0, "receipts": 0, "unmatched": 0}
    settings = (
        await db.execute(select(SdiItSettings).where(SdiItSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()
    if settings is None or not settings.enabled or settings.transport != "pec":
        return counters
    if settings.next_send_after and settings.next_send_after > datetime.now(UTC):
        return counters
    creds = credentials_for(settings)
    if creds is None:
        return counters

    for row in await _due_pending(db, clinic_id):
        row.attempts += 1
        row.transport = "pec"
        await db.commit()  # release the row lock before the network call
        try:
            message_id = await pec_transport.send_file(
                creds, settings.sdi_pec_address, row.file_name, row.xml_payload
            )
        except pec_transport.PecError as exc:
            row.error_message = str(exc)[:500]
            if row.attempts >= MAX_ATTEMPTS:
                row.error_code = "PEC"
                row.next_attempt_at = None
                row.state = "failed"
            else:
                row.next_attempt_at = datetime.now(UTC) + _backoff(row.attempts)
            counters["failed"] += 1
            await sync_invoice_state(db, row)
            # A mailbox-level failure hits every row the same way: pause the clinic.
            settings.last_error = f"PEC: {exc}"[:500]
            settings.next_send_after = datetime.now(UTC) + timedelta(minutes=10)
            await db.commit()
            return counters
        row.state = "exported"
        row.sent_at = datetime.now(UTC)
        row.message_id = message_id[:255] or None
        row.error_message = None
        row.next_attempt_at = None
        settings.last_error = None
        counters["sent"] += 1
        await sync_invoice_state(db, row)
        await db.commit()

    # Receipts: poll the mailbox (network, no locks held), then apply each.
    try:
        poll = await pec_transport.poll_receipts(creds)
    except pec_transport.PecError as exc:
        settings.last_error = f"PEC: {exc}"[:500]
        settings.last_pec_poll_at = datetime.now(UTC)
        await db.commit()
        return counters
    settings.last_pec_poll_at = datetime.now(UTC)
    if poll.sdi_reply_address and poll.sdi_reply_address != settings.sdi_pec_address:
        settings.sdi_pec_address = poll.sdi_reply_address
    for inbound in poll.receipts:
        try:
            await apply_receipt(db, clinic_id, inbound.xml, receipt_file_name=inbound.file_name)
            counters["receipts"] += 1
        except ReceiptError as exc:
            counters["unmatched"] += 1
            logger.info("sdi_it: receipt %s not applied: %s", inbound.file_name, exc)
    await db.commit()
    return counters


async def process_all(session_maker) -> dict[str, int]:
    totals = {"sent": 0, "failed": 0, "receipts": 0, "unmatched": 0}
    async with session_maker() as db:
        clinic_ids = list(
            (
                await db.execute(
                    select(SdiItSettings.clinic_id).where(
                        SdiItSettings.enabled.is_(True), SdiItSettings.transport == "pec"
                    )
                )
            )
            .scalars()
            .all()
        )
    for clinic_id in clinic_ids:
        async with session_maker() as db:
            try:
                counters = await process_clinic(db, clinic_id)
            except Exception:  # noqa: BLE001 - one clinic must not stop the others
                logger.exception("sdi_it: PEC tick failed for clinic %s", clinic_id)
                continue
        for k, v in counters.items():
            totals[k] += v
    return totals
