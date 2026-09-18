"""The routing contract: new person to a lead, known patient to a recall.

These are the tests that encode the requirement most likely to regress.
The matrix runs against the services directly (no HTTP) plus one HTTP
case per branch, because the staff outcome union is part of the contract.
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.leads.models import Lead
from app.modules.leads.recall_routing import NOTE_CAP
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
    assert recall.due_month == date(date.today().year, date.today().month, 1)
    assert recall.due_date == date.today()
    assert "Presupuesto de ortodoncia" in (recall.reason_note or "")
    assert "Viene de Instagram." in (recall.reason_note or "")
    # The availability travels to the call list as a language-free token, so
    # the front desk knows when to ring (the recall path has no lead card).
    assert "mon, wed · afternoon" in (recall.reason_note or "")


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

    # The same enquiry twice: one row, one copy of the block.
    await _route(db_session, test_clinic.id)
    await _route(db_session, test_clinic.id)

    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    note = recalls[0].reason_note or ""
    assert note == "Presupuesto de ortodoncia\n\nViene de Instagram.\n\nmon, wed · afternoon", note
    assert "---" not in note

    # A genuinely different enquiry is appended as a second block, not
    # swapped in.
    await _route(db_session, test_clinic.id, description="Segunda consulta")
    recalls = await _recalls(db_session, patient.id)
    assert len(recalls) == 1
    note = recalls[0].reason_note or ""
    assert note.startswith("Presupuesto de ortodoncia")
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
