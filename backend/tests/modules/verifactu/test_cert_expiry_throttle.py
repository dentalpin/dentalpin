"""Daily cert-expiry alert throttle (#1278).

The job runs from a daily 08:00 cron and stamps ``last_expiry_alert_at``
with its own start time. A 24 h window skipped every day whose cron
start was a few ms earlier than the previous day's; the window is now
20 h, below the 24 h period (and the 23 h day of a DST change).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.verifactu.models import VerifactuCertificate
from app.modules.verifactu.services import cert_expiry


def _freeze(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return moment if tz is None else moment.astimezone(tz)

    monkeypatch.setattr(cert_expiry, "datetime", _FrozenDateTime)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def _fake_send(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs["to_email"])
        return SimpleNamespace(is_success=True)

    monkeypatch.setattr(cert_expiry.email_service, "send_templated", _fake_send)
    return calls


async def _seed(db: AsyncSession) -> None:
    clinic = Clinic(
        id=uuid4(),
        name="Clinic Demo",
        tax_id="B12345678",
        address={"city": "Madrid"},
        settings={"country": "ES"},
    )
    admin = User(
        id=uuid4(),
        email=f"admin-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        first_name="Ada",
        last_name="Admin",
    )
    db.add_all([clinic, admin])
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=admin.id, clinic_id=clinic.id, role="admin"))
    db.add(
        VerifactuCertificate(
            id=uuid4(),
            clinic_id=clinic.id,
            pfx_encrypted=b"x",
            password_encrypted="x",
            subject_cn="CLINICA",
            valid_until=datetime(2032, 1, 20, tzinfo=UTC),
            is_active=True,
        )
    )
    await db.commit()


async def _run_at(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession, moment: datetime
) -> list[cert_expiry.ExpiryAlert]:
    _freeze(monkeypatch, moment)
    factory = async_sessionmaker(db.bind, class_=AsyncSession, expire_on_commit=False)
    return await cert_expiry.check_expiring_certs(factory)


@pytest.mark.asyncio
async def test_daily_cron_alerts_every_day_despite_start_jitter(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, sent: list[str]
) -> None:
    await _seed(db_session)
    # The 08:00 cron starts a few ms late, by a different amount each day.
    runs = [
        datetime(2032, 1, 5, 8, 0, 0, 12000, tzinfo=UTC),
        datetime(2032, 1, 6, 8, 0, 0, 7000, tzinfo=UTC),
        datetime(2032, 1, 7, 8, 0, 0, 9000, tzinfo=UTC),
        datetime(2032, 1, 8, 8, 0, 0, 15000, tzinfo=UTC),
    ]
    counts = [len(await _run_at(monkeypatch, db_session, moment)) for moment in runs]

    assert counts == [1, 1, 1, 1]
    assert len(sent) == 4


@pytest.mark.asyncio
async def test_rerun_13h_later_is_throttled_next_days_run_alerts(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, sent: list[str]
) -> None:
    await _seed(db_session)

    first = await _run_at(monkeypatch, db_session, datetime(2032, 1, 5, 8, 0, tzinfo=UTC))
    # A restart re-running the job 13 h later sends nothing.
    again = await _run_at(monkeypatch, db_session, datetime(2032, 1, 5, 21, 0, tzinfo=UTC))
    # The next day's cron run alerts again (window is measured from the first stamp).
    next_day = await _run_at(monkeypatch, db_session, datetime(2032, 1, 6, 8, 0, tzinfo=UTC))

    assert [len(first), len(again), len(next_day)] == [1, 0, 1]
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_23h_gap_of_a_dst_change_still_alerts(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, sent: list[str]
) -> None:
    await _seed(db_session)

    # A scheduler in a DST zone (e.g. Europe/Madrid host): 08:00 local is
    # 07:00 UTC before the spring change and 06:00 UTC after it, so the
    # two consecutive runs are only 23 h apart.
    before = await _run_at(
        monkeypatch, db_session, datetime(2032, 3, 27, 7, 0, 0, 9000, tzinfo=UTC)
    )
    after = await _run_at(monkeypatch, db_session, datetime(2032, 3, 28, 6, 0, 0, 4000, tzinfo=UTC))

    assert [len(before), len(after)] == [1, 1]
