"""The routing contract: new person to a lead, known patient to a recall.

These are the tests that encode the requirement most likely to regress.
The matrix runs against the services directly (no HTTP) plus one HTTP
case per branch, because the staff outcome union is part of the contract.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.leads.models import Lead
from app.modules.leads.recall_routing import (
    _IDENTITY_LABELS,
    NOTE_CAP,
    _clinic_context,
    _local_day,
)
from app.modules.leads.service import LeadIntakeService, LeadService
from app.modules.recalls.models import Recall
from app.modules.recalls.service import RecallFilters, RecallService

from .conftest import STAFF_ROLE, make_headers, make_patient, role_grants

ENQUIRY = {
    "full_name": "Marta Ruiz",
    "phone": "+34 600 111 222",
    "email": "marta@example.com",
    "motive": "Presupuesto de ortodoncia",
    "description": "Viene de Instagram.",
    "availability_days": ["mon", "wed"],
    "availability_slot": "afternoon",
}

# The label the note opens with, per clinic language (the recall note is stored
# text written in the clinic's communication language, not the reader's UI one).
LABEL_EN = "Web form — submitted as"
LABEL_ES = "Formulario web — enviado como"


async def _use_clinic_language(db: AsyncSession, clinic: Clinic, code: str | None) -> None:
    """Set ``clinics.settings.communication_language`` (``None`` removes it)."""
    settings = dict(clinic.settings or {})
    if code is None:
        settings.pop("communication_language", None)
    else:
        settings["communication_language"] = code
    clinic.settings = settings
    await db.commit()


async def _clinic_local_today(db: AsyncSession, clinic: Clinic) -> date:
    """Today in the clinic's timezone, computed with stdlib only.

    Deliberately not the module's own helper: the point is to catch "call
    today" landing on the server's calendar day instead of the clinic's.
    """
    tz_name = (await db.execute(select(Clinic.timezone).where(Clinic.id == clinic.id))).scalar_one()
    return datetime.now(ZoneInfo(tz_name)).date()


async def _leads(db: AsyncSession, clinic_id) -> list[Lead]:
    return list((await db.execute(select(Lead).where(Lead.clinic_id == clinic_id))).scalars())


async def _recalls(db: AsyncSession, patient_id) -> list[Recall]:
    return list((await db.execute(select(Recall).where(Recall.patient_id == patient_id))).scalars())


async def _route(db: AsyncSession, clinic_id, **overrides):
    outcome = await LeadIntakeService.route(
        db, clinic_id, {**ENQUIRY, **overrides}, recommended_by=None
    )
    await db.commit()
    return outcome


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_person_becomes_a_lead(db_session: AsyncSession, test_clinic: Clinic):
    outcome = await _route(db_session, test_clinic.id)

    assert outcome.outcome == "lead_created"
    assert outcome.lead is not None
    leads = await _leads(db_session, test_clinic.id)
    assert len(leads) == 1
    assert leads[0].status == "new"
    assert leads[0].motive == ENQUIRY["motive"]


@pytest.mark.asyncio
async def test_phone_match_becomes_a_recall_not_a_lead(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The stored number and the enquiry are the same number, formatted
    differently — the trailing-9-digits rule is what makes them match."""
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    outcome = await _route(db_session, test_clinic.id)

    assert outcome.outcome == "recall_queued"
    assert await _leads(db_session, test_clinic.id) == []

    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    recall = recalls[0]
    assert recall.priority == "high"
    assert recall.reason == "other"
    assert recall.status == "pending"
    # "Call today" is the clinic's today, not the server's calendar day.
    clinic_today = await _clinic_local_today(db_session, test_clinic)
    assert recall.due_month == date(clinic_today.year, clinic_today.month, 1)
    assert recall.due_date == clinic_today
    assert "Presupuesto de ortodoncia" in (recall.reason_note or "")
    assert "Viene de Instagram." in (recall.reason_note or "")
    # The submitted availability is NOT carried into the call-back: it is a
    # booking window for a first appointment, and the note records what the
    # patient wanted to say. (On this path there is no lead row either, so it
    # is not stored anywhere — pinned here so it cannot come back by accident.)
    note = recall.reason_note or ""
    assert "mon" not in note
    assert "wed" not in note
    assert "afternoon" not in note


@pytest.mark.asyncio
async def test_availability_is_canonicalised_and_optional(
    db_session: AsyncSession, test_clinic: Clinic
):
    """Days are deduped and ordered mon..sun; an enquiry may omit them."""
    outcome = await _route(
        db_session,
        test_clinic.id,
        availability_days=["fri", "mon", "fri", "sun"],
        availability_slot="evening",
    )
    assert outcome.outcome == "lead_created"
    assert outcome.lead is not None
    assert outcome.lead.availability_days == ["mon", "fri", "sun"]
    assert outcome.lead.availability_slot == "evening"

    without = await _route(
        db_session,
        test_clinic.id,
        phone="+34 699 888 777",
        availability_days=None,
        availability_slot=None,
    )
    assert without.lead is not None
    assert without.lead.availability_days is None
    assert without.lead.availability_slot is None


@pytest.mark.asyncio
async def test_email_match_becomes_a_recall(db_session: AsyncSession, test_clinic: Clinic):
    """Different phone, same email — the rule is OR, not AND."""
    patient = await make_patient(
        db_session, test_clinic.id, phone="611999999", email="Marta@Example.com"
    )

    outcome = await _route(db_session, test_clinic.id)

    assert outcome.outcome == "recall_queued"
    assert await _leads(db_session, test_clinic.id) == []
    assert len(await _recalls(db_session, patient.id)) == 1


@pytest.mark.asyncio
async def test_family_phone_recalls_every_match(db_session: AsyncSession, test_clinic: Clinic):
    """One shared phone, three patients: three people need a call."""
    first = await make_patient(db_session, test_clinic.id, first_name="Ana", phone="600111222")
    second = await make_patient(db_session, test_clinic.id, first_name="Luis", phone="600111222")
    third = await make_patient(db_session, test_clinic.id, first_name="Eva", phone="600111222")

    outcome = await _route(db_session, test_clinic.id)

    assert outcome.outcome == "recall_queued"
    assert len(outcome.recalled_patients) == 3
    assert await _leads(db_session, test_clinic.id) == []
    for patient in (first, second, third):
        assert len(await _recalls(db_session, patient.id)) == 1


@pytest.mark.asyncio
async def test_do_not_contact_match_lands_in_needs_review(
    db_session: AsyncSession, test_clinic: Clinic
):
    patient = await make_patient(db_session, test_clinic.id, phone="600111222", do_not_contact=True)

    outcome = await _route(db_session, test_clinic.id)

    assert outcome.outcome == "recall_queued"
    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    assert recalls[0].status == "needs_review"

    # …and therefore absent from the default call list, which filters
    # opted-out patients out (recalls/CLAUDE.md).
    listed, total = await RecallService.list(db_session, test_clinic.id, RecallFilters())
    assert total == 0 and listed == []
    # The needs_review bucket is where the staff find it instead.
    reviewed, reviewed_total = await RecallService.list(
        db_session,
        test_clinic.id,
        RecallFilters(status="needs_review", include_do_not_contact=True),
    )
    assert reviewed_total == 1 and reviewed[0].id == recalls[0].id


@pytest.mark.asyncio
async def test_archived_patient_is_not_a_match(db_session: AsyncSession, test_clinic: Clinic):
    """An archived chart calling back is a reactivation decision, so the
    enquiry takes the normal lead path."""
    await make_patient(
        db_session,
        test_clinic.id,
        phone="600111222",
        email="archived@example.com",
        status="archived",
    )

    outcome = await _route(db_session, test_clinic.id)

    assert outcome.outcome == "lead_created"
    assert len(await _leads(db_session, test_clinic.id)) == 1


@pytest.mark.asyncio
async def test_repeat_match_refreshes_one_recall_and_appends_once(
    db_session: AsyncSession, test_clinic: Clinic
):
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")
    await _use_clinic_language(db_session, test_clinic, "en")

    # The same enquiry twice: one row, one copy of the block.
    await _route(db_session, test_clinic.id)
    await _route(db_session, test_clinic.id)

    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    note = recalls[0].reason_note or ""
    assert note == (
        f"{LABEL_EN}: Marta Ruiz · +34 600 111 222 · marta@example.com"
        "\n\nPresupuesto de ortodoncia\n\nViene de Instagram."
    ), note
    assert "---" not in note

    # A genuinely different enquiry is appended as a second block, not
    # swapped in.
    await _route(db_session, test_clinic.id, description="Segunda consulta")
    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    note = recalls[0].reason_note or ""
    assert note.startswith(f"{LABEL_EN}:")
    assert "Segunda consulta" in note
    assert note.count("\n\n---\n\n") == 1


@pytest.mark.asyncio
async def test_note_append_is_capped_and_never_destructive(
    db_session: AsyncSession, test_clinic: Clinic
):
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    # A staff-written recall with a long note already on the row.
    staff_note = "x" * (NOTE_CAP - 10)
    _, created = await RecallService.create(
        db_session,
        test_clinic.id,
        {
            "patient_id": patient.id,
            "due_month": date.today(),
            "reason": "other",
            "priority": "normal",
            "reason_note": staff_note,
        },
        recommended_by=None,
    )
    assert created is True
    await db_session.commit()

    await _route(db_session, test_clinic.id)

    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    # Appending would blow the cap, so the existing note is left untouched.
    assert recalls[0].reason_note == staff_note


@pytest.mark.asyncio
async def test_staff_note_is_appended_not_overwritten(
    db_session: AsyncSession, test_clinic: Clinic
):
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")
    await RecallService.create(
        db_session,
        test_clinic.id,
        {
            "patient_id": patient.id,
            "due_month": date.today(),
            "reason": "other",
            "priority": "normal",
            "reason_note": "Llamar por la mañana",
        },
        recommended_by=None,
    )
    await db_session.commit()

    await _route(db_session, test_clinic.id)

    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    note = recalls[0].reason_note or ""
    assert note.startswith("Llamar por la mañana")
    assert "Presupuesto de ortodoncia" in note


@pytest.mark.asyncio
async def test_reported_patient_is_the_highest_ranked_match(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The staff contract reports one patient; it must be the phone match."""
    await make_patient(
        db_session, test_clinic.id, first_name="Email", phone="611000000", email="marta@example.com"
    )
    phone_patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    outcome = await _route(db_session, test_clinic.id)

    assert outcome.recalled_patients[0].id == phone_patient.id
    assert len(outcome.recalled_patients) == 2


@pytest.mark.asyncio
async def test_submitted_identity_is_named_in_the_note(
    db_session: AsyncSession, test_clinic: Clinic
):
    """A stranger's words must not read as the patient's own.

    The recall hangs off the *matched patient*, so the submitted name, phone
    and email have nowhere else to live. Without them in the note, the front
    desk reads "cancel my implant surgery" as if the patient wrote it — which
    is what a relative, a one-digit typo or a shared phone number produces.
    """
    patient = await make_patient(
        db_session, test_clinic.id, first_name="Juan", last_name="Garcia", phone="612345678"
    )
    # Pin the language: the label follows the clinic's, and the fixture clinic
    # has no communication_language set (which falls back to Spanish).
    await _use_clinic_language(db_session, test_clinic, "en")

    await _route(
        db_session,
        test_clinic.id,
        full_name="Somebody Else",
        phone="612345678",
        email="stranger@example.com",
        motive="Cancel my implant surgery",
    )

    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    note = recalls[0].reason_note or ""
    # The header is the first thing the caller reads.
    assert note.startswith(f"{LABEL_EN}: Somebody Else · 612345678")
    assert "stranger@example.com" in note
    assert "Cancel my implant surgery" in note
    # The mismatch is the point: the patient's own name is not in the note, so
    # nothing here claims the patient said it.
    assert "Juan" not in note


@pytest.mark.asyncio
async def test_identity_header_is_written_in_the_clinic_language(
    db_session: AsyncSession, test_clinic: Clinic
):
    """Stored notes have no reader locale: the label is the clinic's.

    The app's UI language is a browser-local preference that never reaches the
    API, and intake has no user session at all — so the closest thing to "the
    user's language" is `clinics.settings.communication_language`, and it is
    frozen into the note when the enquiry arrives.
    """
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    await _use_clinic_language(db_session, test_clinic, "es")
    await _route(db_session, test_clinic.id)
    note = (await _recalls(db_session, patient.id))[0].reason_note or ""
    assert note.startswith(f"{LABEL_ES}: Marta Ruiz")
    assert LABEL_EN not in note

    # The clinic switches language later: the new enquiry appends its own block
    # in the new language, in the same recall, and the old block keeps the old
    # one — notes are append-only text, not re-rendered.
    await _use_clinic_language(db_session, test_clinic, "ta")
    await _route(db_session, test_clinic.id, motive="Segunda consulta")
    note = (await _recalls(db_session, patient.id))[0].reason_note or ""
    assert note.count("\n\n---\n\n") == 1
    assert note.startswith(f"{LABEL_ES}: Marta Ruiz")
    assert "இணையதளப் படிவம் — சமர்ப்பிக்கப்பட்டது" in note


@pytest.mark.asyncio
async def test_identity_header_falls_back_when_the_clinic_language_is_unusable(
    db_session: AsyncSession, test_clinic: Clinic
):
    """Unset or unknown language must not crash intake or print a bare `None:`."""
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    await _use_clinic_language(db_session, test_clinic, None)
    await _route(db_session, test_clinic.id)
    note = (await _recalls(db_session, patient.id))[0].reason_note or ""
    assert note.startswith(f"{LABEL_ES}: Marta Ruiz")  # platform default

    await _use_clinic_language(db_session, test_clinic, "xx")
    await _route(db_session, test_clinic.id, motive="Otra consulta")
    note = (await _recalls(db_session, patient.id))[0].reason_note or ""
    assert f"\n\n---\n\n{LABEL_ES}: Marta Ruiz" in note
    assert "None" not in note


def test_identity_labels_cover_every_host_locale():
    """A new UI locale must not silently fall back to Spanish inside stored
    notes. Host locale list: ``core/pdf_locales.PDF_LOCALES`` (guarded against
    the frontend i18n config by its own test)."""
    from app.core.pdf_locales import PDF_LOCALES

    assert set(_IDENTITY_LABELS) == set(PDF_LOCALES)
    assert all(label.strip() for label in _IDENTITY_LABELS.values())


@pytest.mark.asyncio
async def test_clinic_local_day_follows_the_clinic_timezone(
    db_session: AsyncSession, test_clinic: Clinic
):
    """One instant, two clinics, two calendar days.

    Pins the semantics deterministically: a bare ``date.today()`` would answer
    the same thing for both clinics. Exercises the two functions the routing
    path actually uses (`_clinic_context` → `_local_day`).
    """
    instant = datetime(2026, 9, 18, 23, 30, tzinfo=UTC)

    async def local_day() -> date:
        tz, _locale = await _clinic_context(db_session, test_clinic.id)
        return _local_day(tz, instant)

    test_clinic.timezone = "Pacific/Kiritimati"  # UTC+14 -> already tomorrow
    await db_session.commit()
    assert await local_day() == date(2026, 9, 19)

    test_clinic.timezone = "Pacific/Midway"  # UTC-11 -> still today
    await db_session.commit()
    assert await local_day() == date(2026, 9, 18)

    # A hand-edited tz id must not 500 intake.
    test_clinic.timezone = "Not/AZone"
    await db_session.commit()
    assert await local_day() == date(2026, 9, 18)


# ---------------------------------------------------------------------------
# HTTP: the two entry points and the outcome union
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_intake_bodies_are_identical_in_both_end_states(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    """D12: an unauthenticated caller must learn nothing from the body."""
    from app.modules.leads.service import LeadIntakeKeyService

    _, plaintext = await LeadIntakeKeyService.rotate(db_session, test_clinic.id)
    await db_session.commit()

    payload = {**ENQUIRY, "website": ""}
    unmatched = await client.post(
        "/api/v1/leads/public/intake", json=payload, headers={"X-Lead-Key": plaintext}
    )
    await make_patient(db_session, test_clinic.id, phone="600111222")
    matched = await client.post(
        "/api/v1/leads/public/intake", json=payload, headers={"X-Lead-Key": plaintext}
    )

    assert unmatched.status_code == matched.status_code == 201
    assert unmatched.content == matched.content


@pytest.mark.asyncio
async def test_staff_create_returns_the_recall_outcome(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    patient = await make_patient(db_session, test_clinic.id, phone="600111222")

    response = await client.post("/api/v1/leads/", json=ENQUIRY, headers=auth_headers)
    assert response.status_code == 201, response.text
    data = response.json()["data"]

    assert data["outcome"] == "recall_queued"
    assert data["lead"] is None
    assert data["recalled_patient"]["id"] == str(patient.id)
    assert data["recalled_patient"]["first_name"] == patient.first_name
    # The enquiry did not become a lead card.
    assert await _leads(db_session, test_clinic.id) == []
    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    # recommended_by records the staff member who took the enquiry.
    assert recalls[0].recommended_by is not None


@pytest.mark.asyncio
async def test_staff_create_requires_patients_read(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    """It discloses the matched patient — so it needs that permission."""
    headers = await make_headers(db_session, test_clinic.id, role=STAFF_ROLE)
    await make_patient(db_session, test_clinic.id, phone="600111222")

    with role_grants(STAFF_ROLE, []):
        denied = await client.post("/api/v1/leads/", json=ENQUIRY, headers=headers)
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_staff_create_keeps_the_routing_rule(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    """Same rule as the public form: an unmatched enquiry is a lead card."""
    response = await client.post(
        "/api/v1/leads/",
        json={**ENQUIRY, "phone": "+34 699 888 777"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["outcome"] == "lead_created"
    assert data["recalled_patient"] is None
    assert data["lead"]["status"] == "new"


@pytest.mark.asyncio
async def test_create_lead_strips_intake_only_fields(db_session: AsyncSession, test_clinic: Clinic):
    """The single insert path never persists the honeypot."""
    lead = await LeadService.create_lead(
        db_session,
        test_clinic.id,
        {"full_name": "Solo", "phone": "699000000", "motive": "x", "website": "bot"},
    )
    await db_session.commit()
    assert lead.status == "new"
    assert not hasattr(lead, "website")
