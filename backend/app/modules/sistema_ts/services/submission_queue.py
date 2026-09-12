"""Worker: sync new documents, then send due ``pending`` rows one by one to
the Sistema TS synchronous service. Rows are locked ``FOR UPDATE SKIP
LOCKED`` and the session commits before every network call (the
nav_online/sdi_it posture). Transport errors back off
``min(120·2^(attempts-1), 3600)`` s up to ``max_attempts``; a credential
failure pauses the clinic ten minutes. Business rejections (esito 1) are
terminal ``rejected`` with the E messages for the admin."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password

from ..models import SistemaTsDocument, SistemaTsSettings
from . import ts_client
from .documents import DocumentError, build_request, sync_clinic

logger = logging.getLogger(__name__)

_BATCH = 20


def credentials_ok(settings: SistemaTsSettings) -> bool:
    return bool(
        settings.username
        and settings.password_encrypted
        and settings.pincode_encrypted
        and settings.cf_proprietario
    )


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(120 * (2 ** max(attempts - 1, 0)), 3600))


async def _due(db: AsyncSession, clinic_id: UUID) -> list[SistemaTsDocument]:
    now = datetime.now(UTC)
    stmt = (
        select(SistemaTsDocument)
        .where(
            SistemaTsDocument.clinic_id == clinic_id,
            SistemaTsDocument.state == "pending",
            (SistemaTsDocument.next_attempt_at.is_(None))
            | (SistemaTsDocument.next_attempt_at <= now),
        )
        .order_by(SistemaTsDocument.created_at)
        .limit(_BATCH)
        .with_for_update(skip_locked=True)
    )
    return list((await db.execute(stmt)).scalars().all())


def _apply_response(doc: SistemaTsDocument, resp: ts_client.TsResponse) -> str:
    now = datetime.now(UTC)
    doc.response_xml = resp.raw
    doc.esito = resp.esito
    doc.messages = resp.messages or None
    doc.protocollo = resp.protocollo
    if resp.esito == 0:
        doc.state = "accepted"
    elif resp.esito == 2:
        doc.state = "accepted_with_warnings"
    else:
        doc.state = "rejected"
        doc.error_message = (
            "; ".join(f"{m.get('codice')}: {m.get('descrizione')}" for m in resp.blocking_messages)[
                :2000
            ]
            or "esitoChiamata=1"
        )
    doc.finished_at = now
    return doc.state


async def process_clinic(db: AsyncSession, clinic_id: UUID) -> dict[str, int]:
    counters = {"queued": 0, "accepted": 0, "rejected": 0, "failed": 0}
    settings = (
        await db.execute(select(SistemaTsSettings).where(SistemaTsSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()
    if settings is None or not settings.enabled or not credentials_ok(settings):
        return counters
    if settings.next_send_after and settings.next_send_after > datetime.now(UTC):
        return counters

    try:
        synced = await sync_clinic(db, settings)
        counters["queued"] = synced["inserimento"] + synced["rimborso"] + synced["cancellazione"]
        await db.commit()
    except DocumentError as exc:
        settings.last_error = str(exc)[:500]
        await db.commit()
        return counters

    password = decrypt_password(settings.password_encrypted)
    for doc in await _due(db, clinic_id):
        doc.attempts += 1
        doc.state = "sending"
        try:
            doc.request_xml = await build_request(db, settings, doc)
        except DocumentError as exc:
            doc.state = "rejected"
            doc.error_message = str(exc)[:500]
            doc.finished_at = datetime.now(UTC)
            counters["rejected"] += 1
            await db.commit()
            continue
        doc.sent_at = datetime.now(UTC)
        await db.commit()  # release the lock before the network call
        try:
            resp = await ts_client.send(
                doc.request_xml,
                environment=settings.environment,
                username=settings.username,
                password=password,
            )
        except ts_client.TsClientError as exc:
            doc.error_message = str(exc)[:500]
            if doc.attempts >= doc.max_attempts:
                doc.state = "failed"
                doc.finished_at = datetime.now(UTC)
            else:
                doc.state = "pending"
                doc.next_attempt_at = datetime.now(UTC) + _backoff(doc.attempts)
            counters["failed"] += 1
            settings.last_error = f"Sistema TS: {exc}"[:500]
            if "credenziali" in str(exc):
                settings.next_send_after = datetime.now(UTC) + timedelta(minutes=10)
            await db.commit()
            if settings.next_send_after:
                return counters
            continue
        settings.last_response_at = datetime.now(UTC)
        settings.last_error = None
        state = _apply_response(doc, resp)
        counters["accepted" if state.startswith("accepted") else "rejected"] += 1
        await db.commit()
    return counters


async def process_all(session_maker) -> dict[str, int]:
    totals = {"queued": 0, "accepted": 0, "rejected": 0, "failed": 0}
    async with session_maker() as db:
        clinic_ids = list(
            (
                await db.execute(
                    select(SistemaTsSettings.clinic_id).where(SistemaTsSettings.enabled.is_(True))
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
                logger.exception("sistema_ts: tick failed for clinic %s", clinic_id)
                continue
        for k, v in counters.items():
            totals[k] += v
    return totals
