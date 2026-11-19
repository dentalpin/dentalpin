"""Transactionally enqueue encrypted booking messages and dispatch after commit."""

import html
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password, encrypt_password
from app.core.email.providers.base import EmailMessage

from .delivery import deliver
from .models import BookingMail, BookingRequest


def enqueue(db: AsyncSession, clinic_id: UUID, request_id: UUID, kind: str, payload: dict) -> None:
    db.add(
        BookingMail(
            clinic_id=clinic_id,
            request_id=request_id,
            kind=kind,
            payload_encrypted=encrypt_password(json.dumps(payload)),
            attempts=0,
        )
    )


async def dispatch_one(db: AsyncSession) -> bool:
    mail = await db.scalar(
        select(BookingMail)
        .where(
            or_(
                BookingMail.next_attempt_at.is_(None),
                BookingMail.next_attempt_at <= datetime.now(UTC),
            )
        )
        .order_by(BookingMail.created_at, BookingMail.id)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
        .limit(1)
    )
    if mail is None:
        return False
    row = await db.get(BookingRequest, mail.request_id)
    now = datetime.now(UTC)
    if row is None or (
        mail.kind == "confirmation"
        and (
            row.status != "pending_confirmation"
            or row.confirmation_deadline <= now
            or row.start_time <= now
        )
    ):
        await db.delete(mail)
        return True
    plaintext = decrypt_password(mail.payload_encrypted)
    if not plaintext:
        # Preserve the encrypted item for a possible key recovery; do not
        # expose its contents or repeatedly retry within the same tick.
        mail.attempts += 1
        mail.next_attempt_at = now + timedelta(hours=1)
        return True
    payload = json.loads(plaintext)
    text = payload["text"]
    body_html = f"<p>{html.escape(text)}</p>"
    if mail.kind == "confirmation":
        body_html = (
            f'<p><a href="{html.escape(payload["link"], quote=True)}">Confirm request</a></p>'
        )
    try:
        await deliver(
            db,
            mail.clinic_id,
            EmailMessage(
                to_email=payload["email"],
                subject=payload["subject"],
                body_text=text,
                body_html=body_html,
            ),
        )
    except Exception:
        mail.attempts += 1
        # Slow down repeated failures; retention cleanup eventually deletes
        # rejected requests and their encrypted mail via the foreign key.
        mail.next_attempt_at = now + timedelta(minutes=60 if mail.attempts >= 20 else 1)
        return True
    await db.delete(mail)
    return True
