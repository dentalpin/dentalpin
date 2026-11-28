"""Daily check for soon-to-expire Verifactu certificates.

Wired to APScheduler from :mod:`app.modules.verifactu.tasks`. Sends an
email to every admin of a clinic whose active certificate will expire
within :data:`THRESHOLD_DAYS`. Throttled per certificate to one batch
of alerts per daily run via ``VerifactuCertificate.last_expiry_alert_at``.

The throttle window is :data:`THROTTLE_HOURS` (20 h), deliberately
below the 24 h cron period: each run stamps its own start time, and with
a 24 h window a start a few ms earlier than yesterday's left the old
stamp under 24 h old, so the "daily" alert skipped about half of all
days (#1278). 20 h absorbs start jitter and the 23 h day of a DST
change in the scheduler's zone, and still blocks a same-day rerun.

The clinic's certificate matters for AEAT submissions (mTLS handshake);
once it expires the worker stops being able to send and the queue
backs up silently. This job surfaces the problem early so an admin can
reissue / re-upload before reaching the deadline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.email import email_service

from ..models import VerifactuCertificate

logger = logging.getLogger(__name__)

THRESHOLD_DAYS = 30
THROTTLE_HOURS = 20


@dataclass
class ExpiryAlert:
    """Bookkeeping for a single cert checked by the job."""

    certificate_id: UUID
    clinic_id: UUID
    days_left: int
    sent_to: list[str]


async def _admins_for(db: AsyncSession, clinic_id: UUID) -> list[User]:
    result = await db.execute(
        select(User)
        .join(ClinicMembership, ClinicMembership.user_id == User.id)
        .where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.role == "admin",
            User.is_active.is_(True),
        )
    )
    return list(result.scalars())


async def _clinic_name(db: AsyncSession, clinic_id: UUID) -> str:
    result = await db.execute(select(Clinic.name).where(Clinic.id == clinic_id))
    row = result.first()
    return (row[0] if row else "") or ""


async def check_expiring_certs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    threshold_days: int = THRESHOLD_DAYS,
    throttle_hours: int = THROTTLE_HOURS,
) -> list[ExpiryAlert]:
    """Scan active certificates and email admins of those expiring soon.

    Args:
        session_factory: Async session maker (typically
            :data:`app.database.async_session_maker`).
        threshold_days: Alert when ``valid_until`` is within this many
            days. Already-expired certs (negative ``days_left``) are
            included.
        throttle_hours: Skip a certificate if its
            ``last_expiry_alert_at`` is newer than ``now - throttle_hours``.

    Returns:
        One :class:`ExpiryAlert` per certificate processed (including
        ones that were skipped due to no admins). Useful for tests and
        logging.
    """

    now = datetime.now(UTC)
    cutoff = now + timedelta(days=threshold_days)
    throttle_cutoff = now - timedelta(hours=throttle_hours)

    async with session_factory() as db:
        result = await db.execute(
            select(VerifactuCertificate).where(
                VerifactuCertificate.is_active.is_(True),
                VerifactuCertificate.valid_until.is_not(None),
                VerifactuCertificate.valid_until <= cutoff,
            )
        )
        certs = list(result.scalars())

        alerts: list[ExpiryAlert] = []
        for cert in certs:
            if (
                cert.last_expiry_alert_at is not None
                and cert.last_expiry_alert_at >= throttle_cutoff
            ):
                continue

            assert cert.valid_until is not None
            days_left = (cert.valid_until - now).days
            admins = await _admins_for(db, cert.clinic_id)
            clinic_name = await _clinic_name(db, cert.clinic_id)

            sent_to: list[str] = []
            for admin in admins:
                ctx = {
                    "admin_name": admin.full_name,
                    "clinic_name": clinic_name,
                    "subject_cn": cert.subject_cn or "",
                    "valid_until": cert.valid_until,
                    "days_left": days_left,
                    "is_expired": days_left < 0,
                }
                subject = (
                    "Tu certificado Verifactu ya ha caducado"
                    if days_left < 0
                    else "Tu certificado Verifactu caduca pronto"
                )
                try:
                    res = await email_service.send_templated(
                        to_email=admin.email,
                        to_name=admin.full_name,
                        template_key="verifactu_cert_expiry",
                        context=ctx,
                        subject=subject,
                        locale="es",
                        db=db,
                        clinic_id=cert.clinic_id,
                    )
                    if res.is_success:
                        sent_to.append(admin.email)
                except Exception:  # noqa: BLE001 — don't let one admin's failure block others
                    logger.exception(
                        "verifactu cert-expiry: failed to email admin %s for clinic %s",
                        admin.id,
                        cert.clinic_id,
                    )

            cert.last_expiry_alert_at = now
            alerts.append(
                ExpiryAlert(
                    certificate_id=cert.id,
                    clinic_id=cert.clinic_id,
                    days_left=days_left,
                    sent_to=sent_to,
                )
            )

        if alerts:
            await db.commit()
            logger.info("verifactu cert-expiry: alerted %d certificates", len(alerts))

        return alerts
