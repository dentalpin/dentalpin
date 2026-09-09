"""Submission worker for ``nav_online_records`` (issue #341).

``process_clinic`` drains one clinic's queue: pending rows are sent one
operation per ``manageInvoice`` request (phase 1 — batching up to NAV's
100/request is a later optimisation), then rows in ``sent`` are polled
with ``queryTransactionStatus`` until DONE/ABORTED. Rows are locked
``FOR UPDATE SKIP LOCKED`` so overlapping ticks never double-send, and
the session commits *before* each network call so no row lock is held
across I/O — the notifications/integrations outbox posture.

Transport errors back off ``min(60·2^(attempts-1), 3600)`` seconds and
give up at ``max_attempts``; NAV business rejections are terminal
(``rejected``) and surface in the records UI for the admin to fix and
retry after correcting the invoice.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password

from ..models import NavOnlineRecord, NavOnlineSettings
from . import nav_client

logger = logging.getLogger(__name__)

_BATCH = 20
_TERMINAL_OK = {"DONE"}
_TERMINAL_BAD = {"ABORTED"}


def credentials_for(settings: NavOnlineSettings) -> nav_client.Credentials | None:
    if not (
        settings.technical_user_login
        and settings.technical_user_password_encrypted
        and settings.signature_key_encrypted
        and settings.exchange_key_encrypted
        and settings.tax_number
    ):
        return None
    return nav_client.Credentials(
        login=settings.technical_user_login,
        password=decrypt_password(settings.technical_user_password_encrypted),
        signature_key=decrypt_password(settings.signature_key_encrypted),
        exchange_key=decrypt_password(settings.exchange_key_encrypted),
        tax_number=settings.tax_number[:8],
        software_id=settings.software_id,
        software_dev_contact=settings.software_dev_contact,
    )


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(60 * (2 ** max(attempts - 1, 0)), 3600))


async def _due_rows(db: AsyncSession, clinic_id: UUID, state: str) -> list[NavOnlineRecord]:
    now = datetime.now(UTC)
    stmt = (
        select(NavOnlineRecord)
        .where(
            NavOnlineRecord.clinic_id == clinic_id,
            NavOnlineRecord.state == state,
            (NavOnlineRecord.next_attempt_at.is_(None)) | (NavOnlineRecord.next_attempt_at <= now),
        )
        .order_by(NavOnlineRecord.created_at)
        .limit(_BATCH)
        .with_for_update(skip_locked=True)
    )
    return list((await db.execute(stmt)).scalars().all())


async def process_clinic(db: AsyncSession, clinic_id: UUID) -> dict[str, int]:
    """Send pending rows, then poll sent rows. Returns counters."""
    counters = {"sent": 0, "done": 0, "rejected": 0, "failed": 0}
    settings = (
        await db.execute(select(NavOnlineSettings).where(NavOnlineSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()
    if settings is None or not settings.enabled:
        return counters
    if settings.next_send_after and settings.next_send_after > datetime.now(UTC):
        return counters
    creds = credentials_for(settings)
    if creds is None:
        return counters

    pending = await _due_rows(db, clinic_id, "pending") + await _due_rows(db, clinic_id, "failed")
    if pending:
        token: str | None = None
        try:
            token = await nav_client.exchange_token(creds, settings.environment)
        except nav_client.NavClientError as exc:
            # Credentials/transport problem affects the whole clinic: pause it.
            settings.last_error = f"tokenExchange: {exc}"[:500]
            settings.next_send_after = datetime.now(UTC) + timedelta(minutes=10)
            await db.commit()
            return counters

        for row in pending:
            row.state = "sending"
            row.attempts += 1
            await db.commit()  # release the lock before the network call
            try:
                resp = await nav_client.manage_invoice(
                    creds, settings.environment, token, [(row.operation, row.xml_payload)]
                )
            except nav_client.NavClientError as exc:
                _mark_failed(row, str(exc))
                counters["failed"] += 1
                await db.commit()
                continue
            settings.last_nav_response_at = datetime.now(UTC)
            if resp.ok and resp.transaction_id:
                row.state = "sent"
                row.transaction_id = resp.transaction_id
                row.sent_at = datetime.now(UTC)
                row.error_code = None
                row.error_message = None
                counters["sent"] += 1
            else:
                # A business error on submit (bad signature, schema) is a
                # clinic-side problem; keep the row retryable but surface it.
                _mark_failed(row, f"{resp.error_code}: {resp.message}")
                counters["failed"] += 1
            await db.commit()

    for row in await _due_rows(db, clinic_id, "sent"):
        if not row.transaction_id:
            continue
        await db.commit()
        try:
            resp = await nav_client.query_transaction_status(
                creds, settings.environment, row.transaction_id
            )
        except nav_client.NavClientError as exc:
            row.next_attempt_at = datetime.now(UTC) + timedelta(minutes=2)
            row.error_message = str(exc)[:500]
            await db.commit()
            continue
        settings.last_nav_response_at = datetime.now(UTC)
        result = next((p for p in resp.processing if p.index == 1), None)
        if result is None:
            row.next_attempt_at = datetime.now(UTC) + timedelta(minutes=2)
        else:
            row.nav_status = result.invoice_status
            if result.invoice_status in _TERMINAL_OK:
                row.state = "done"
                row.finished_at = datetime.now(UTC)
                counters["done"] += 1
            elif result.invoice_status in _TERMINAL_BAD or result.error_code:
                row.state = "rejected"
                row.error_code = result.error_code
                row.error_message = result.message
                row.finished_at = datetime.now(UTC)
                counters["rejected"] += 1
            else:
                row.next_attempt_at = datetime.now(UTC) + timedelta(minutes=2)
        await db.commit()

    settings.last_error = None
    await db.commit()
    return counters


def _mark_failed(row: NavOnlineRecord, error: str) -> None:
    row.error_message = error[:500]
    if row.attempts >= row.max_attempts:
        row.state = "aborted"
        row.finished_at = datetime.now(UTC)
    else:
        row.state = "failed"
        row.next_attempt_at = datetime.now(UTC) + _backoff(row.attempts)


async def process_all(session_factory) -> dict[str, int]:
    """Scheduler entry point: every enabled clinic, each in its own session."""
    totals = {"sent": 0, "done": 0, "rejected": 0, "failed": 0}
    async with session_factory() as db:
        clinic_ids = list(
            (
                await db.execute(
                    select(NavOnlineSettings.clinic_id).where(NavOnlineSettings.enabled.is_(True))
                )
            ).scalars()
        )
    for clinic_id in clinic_ids:
        async with session_factory() as db:
            try:
                c = await process_clinic(db, clinic_id)
            except Exception as exc:  # noqa: BLE001 — one clinic must not stop the others
                logger.error("nav_online: clinic %s tick failed: %s", clinic_id, exc, exc_info=True)
                continue
            for k in totals:
                totals[k] += c.get(k, 0)
    return totals
