"""Telephony service: normalization, caller matching, ingest lifecycle."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password
from app.modules.patients.models import Patient
from app.modules.telephony.models import TelephonySettings
from app.modules.telephony.service import TelephonyService, normalize_number


async def _settings(db, clinic_id, *, country="ES") -> TelephonySettings:
    s = TelephonySettings(
        clinic_id=clinic_id,
        signing_secret_encrypted=encrypt_password("tel_secret"),
        default_country=country,
        is_active=True,
    )
    db.add(s)
    await db.commit()
    return s


async def _patient(db, clinic_id, *, phone, first="Ana", last="García") -> Patient:
    p = Patient(clinic_id=clinic_id, first_name=first, last_name=last, phone=phone)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


# --- normalization -------------------------------------------------------


def test_normalize_local_number_uses_default_country():
    assert normalize_number("600 11 22 33", "ES") == "+34600112233"
    assert normalize_number("+34 600 11 22 33", "ES") == "+34600112233"


def test_normalize_unparseable_returns_input():
    assert normalize_number("anonymous", "ES") == "anonymous"
    assert normalize_number(None, "ES") is None


# --- matching ------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_match_by_normalized_phone(db_session: AsyncSession, test_clinic):
    p = await _patient(db_session, test_clinic.id, phone="600 11 22 33")
    match = await TelephonyService.match_patient(db_session, test_clinic.id, "+34600112233")
    assert match is not None and match.id == p.id


@pytest.mark.asyncio
async def test_multiple_matches_return_none(db_session: AsyncSession, test_clinic):
    await _patient(db_session, test_clinic.id, phone="+34600112233")
    await _patient(db_session, test_clinic.id, phone="600112233", first="Luis")
    match = await TelephonyService.match_patient(db_session, test_clinic.id, "+34600112233")
    assert match is None


@pytest.mark.asyncio
async def test_no_match_returns_none(db_session: AsyncSession, test_clinic):
    assert await TelephonyService.match_patient(db_session, test_clinic.id, "+34999888777") is None


# --- ingest lifecycle ----------------------------------------------------


def _event(event, call_id="c-1", **kw):
    base = {
        "event": event,
        "call_id": call_id,
        "direction": "inbound",
        "from_number": "600 11 22 33",
        "to_number": "+34910000000",
        "provider": "webhook",
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_ringing_answered_ended_lifecycle(db_session: AsyncSession, test_clinic):
    settings = await _settings(db_session, test_clinic.id)
    patient = await _patient(db_session, test_clinic.id, phone="600112233")

    row = await TelephonyService.ingest_event(db_session, settings, _event("call.ringing"))
    assert row.status == "ringing"
    assert row.from_number == "+34600112233"
    assert row.patient_id == patient.id
    assert row.started_at is not None

    row2 = await TelephonyService.ingest_event(db_session, settings, _event("call.answered"))
    assert row2.id == row.id  # same call row, updated
    assert row2.status == "answered"
    assert row2.answered_at is not None

    row3 = await TelephonyService.ingest_event(
        db_session, settings, _event("call.ended", duration_seconds=47)
    )
    assert row3.id == row.id
    assert row3.status == "ended"
    assert row3.duration_seconds == 47
    assert row3.ended_at is not None


@pytest.mark.asyncio
async def test_ended_without_answer_becomes_missed(db_session: AsyncSession, test_clinic):
    settings = await _settings(db_session, test_clinic.id)
    await TelephonyService.ingest_event(db_session, settings, _event("call.ringing", call_id="c-2"))
    row = await TelephonyService.ingest_event(
        db_session, settings, _event("call.ended", call_id="c-2")
    )
    assert row.status == "missed"


@pytest.mark.asyncio
async def test_unusable_event_is_ignored(db_session: AsyncSession, test_clinic):
    settings = await _settings(db_session, test_clinic.id)
    assert (
        await TelephonyService.ingest_event(db_session, settings, {"event": "call.exotic"}) is None
    )
    assert (
        await TelephonyService.ingest_event(
            db_session, settings, _event("call.ringing", call_id="")
        )
        is None
    )


@pytest.mark.asyncio
async def test_unknown_caller_event_published(db_session: AsyncSession, test_clinic):
    from app.core.events import EventType, event_bus

    settings = await _settings(db_session, test_clinic.id)
    seen: list[dict] = []

    async def capture(data, *, db):
        seen.append(data)

    event_bus.subscribe(EventType.CALL_UNKNOWN_CALLER, capture)
    try:
        row = await TelephonyService.ingest_event(
            db_session, settings, _event("call.ringing", call_id="c-3", from_number="+34999888777")
        )
        assert row.patient_id is None
        assert len(seen) == 1
        assert seen[0]["call_log_id"] == str(row.id)
    finally:
        event_bus.unsubscribe(EventType.CALL_UNKNOWN_CALLER, capture)


@pytest.mark.asyncio
async def test_first_event_race_adopts_winner_row(
    db_session: AsyncSession, test_clinic, monkeypatch
):
    """Two simultaneous first events of one call: the loser of the unique
    constraint must adopt the winner's row instead of raising."""
    from sqlalchemy import text

    settings = await _settings(db_session, test_clinic.id)

    original = TelephonyService.match_patient

    async def match_and_race(db, clinic_id, number, **kwargs):
        # Simulate the concurrent writer landing between our SELECT (which
        # found nothing) and our INSERT: the row exists by flush time.
        await db.execute(
            text(
                "INSERT INTO telephony_call_logs "
                "(id, clinic_id, provider, call_id, direction, from_number, status, "
                " created_at, updated_at) "
                "VALUES (gen_random_uuid(), :clinic, 'webhook', 'c-race', 'inbound', "
                " '+34600112233', 'ringing', now(), now())"
            ),
            {"clinic": str(clinic_id)},
        )
        return await original(db, clinic_id, number, **kwargs)

    monkeypatch.setattr(TelephonyService, "match_patient", match_and_race)
    row = await TelephonyService.ingest_event(
        db_session, settings, _event("call.answered", call_id="c-race")
    )
    assert row is not None
    assert row.call_id == "c-race"
    assert row.status == "answered"  # the update still applied to the winner's row

    from sqlalchemy import func, select

    from app.modules.telephony.models import CallLog

    count = (
        await db_session.execute(
            select(func.count()).select_from(CallLog).where(CallLog.call_id == "c-race")
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "caller",
    [
        "+447600112233",  # UK mobile whose last nine digits are a Spanish patient's
        "203456",  # an internal extension: six digits, the tail of a patient's number
    ],
)
async def test_a_different_number_with_the_same_tail_links_nobody(
    db_session: AsyncSession, test_clinic, caller: str
):
    """The match is confirmed on the whole normalized number (#973).

    The module contract says SQL narrows on the last digits and Python
    confirms on the full normalized value, but the Python step re-checked
    the same nine-digit tail, so any number sharing it put that patient's
    record on screen.
    """
    settings = await _settings(db_session, test_clinic.id)
    await _patient(db_session, test_clinic.id, phone="+34 600 112 233")
    await _patient(db_session, test_clinic.id, phone="+34 910 203 456", first="Eva")

    row = await TelephonyService.ingest_event(
        db_session, settings, _event("call.ringing", call_id=f"t-{caller}", from_number=caller)
    )
    assert row.patient_id is None


@pytest.mark.asyncio
async def test_the_same_number_in_another_format_still_matches(
    db_session: AsyncSession, test_clinic
):
    settings = await _settings(db_session, test_clinic.id)
    patient = await _patient(db_session, test_clinic.id, phone="0034 600-11-22-33")
    row = await TelephonyService.ingest_event(
        db_session, settings, _event("call.ringing", call_id="fmt-1", from_number="600112233")
    )
    assert row.patient_id == patient.id
