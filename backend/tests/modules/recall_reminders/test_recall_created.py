"""recall_reminders: RECALL_CREATED -> notification enqueue.

Covers the module's only real behavior: when a recall is created, the
handler enqueues a reminder via NotificationGateway, scoped to the
correct clinic, and does nothing for any other clinic's data.

Transactional (ADR 0019): the handler takes the caller's session and
runs inside a savepoint rather than opening its own — these tests call
it directly with db_session and assert on that same session, the way
a publisher (recalls/service.py) would.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.models import CommunicationMessage
from app.modules.patients.models import Patient
from app.modules.recall_reminders.handlers import _humanize_due_month, _on_recall_created


@pytest.mark.asyncio
async def test_recall_created_enqueues_reminder_for_correct_clinic_only(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    other_clinic = Clinic(
        id=uuid4(), name="Other Clinic", tax_id="B99999999", address={}, settings={}
    )
    db_session.add(other_clinic)
    await db_session.commit()

    await _on_recall_created(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
            "recall_id": str(uuid4()),
            "reason": "6-month checkup",
            "due_month": "2026-09-01",
        },
        db=db_session,
    )

    rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(CommunicationMessage.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].patient_id == test_patient.id
    assert (
        rows[0].context_data["patient_name"]
        == f"{test_patient.first_name} {test_patient.last_name}"
    )
    assert rows[0].context_data["clinic_name"] == test_clinic.name
    # The test clinic sets no communication language: Spanish, the default.
    assert rows[0].context_data["due_month"] == "septiembre de 2026"

    other_rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == other_clinic.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert other_rows == []


@pytest.mark.asyncio
async def test_recall_created_is_idempotent_on_dedup_key(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """Same recall_id firing twice (e.g. a redelivered event) must not
    enqueue two reminders — the handler always sets dedup_key from
    recall_id specifically to guard against this."""
    recall_id = str(uuid4())
    payload = {
        "clinic_id": str(test_clinic.id),
        "patient_id": str(test_patient.id),
        "recall_id": recall_id,
        "reason": "6-month checkup",
        "due_month": "2026-09-01",
    }

    await _on_recall_created(payload, db=db_session)
    await _on_recall_created(payload, db=db_session)

    rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(CommunicationMessage.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_recall_created_skips_silently_when_patient_missing(
    db_session: AsyncSession, test_clinic: Clinic
):
    """A patient_id that doesn't resolve (deleted between flush and
    publish, or a bad payload) must not raise inside the publisher's
    transaction — this handler is best-effort by design."""
    await _on_recall_created(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(uuid4()),
            "recall_id": str(uuid4()),
            "reason": "6-month checkup",
            "due_month": "2026-09-01",
        },
        db=db_session,
    )

    rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(CommunicationMessage.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


def test_humanize_due_month():
    assert _humanize_due_month("2026-09-01") == "September 2026"
    assert _humanize_due_month("2026-09-01", "es") == "septiembre de 2026"
    assert _humanize_due_month("2026-09-01", "xx") == "September 2026"
    assert _humanize_due_month(None) is None
    assert _humanize_due_month("not-a-date") == "not-a-date"


async def _due_month_sent(db_session: AsyncSession, clinic_id, patient_id) -> str:
    await _on_recall_created(
        {
            "clinic_id": str(clinic_id),
            "patient_id": str(patient_id),
            "recall_id": str(uuid4()),
            "reason": "hygiene",
            "due_month": "2026-09-01",
        },
        db=db_session,
    )
    row = (
        await db_session.execute(
            select(CommunicationMessage)
            .where(CommunicationMessage.patient_id == patient_id)
            .order_by(CommunicationMessage.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    return row.context_data["due_month"]


@pytest.mark.asyncio
async def test_due_month_is_written_in_the_language_the_message_is_sent_in(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The reminder's month follows the message locale (#975).

    ``strftime("%B %Y")`` always produced English, so the Spanish template
    read "para September 2026". The locale is the one the gateway renders
    the template in: the patient's preference, else the clinic's
    communication language.
    """
    from app.modules.notifications.models import NotificationPreference

    test_clinic.settings = {**(test_clinic.settings or {}), "communication_language": "es"}
    ana = Patient(clinic_id=test_clinic.id, first_name="Ana", last_name="Ruiz", email="a@x.es")
    luc = Patient(clinic_id=test_clinic.id, first_name="Luc", last_name="Bern", email="l@x.fr")
    db_session.add_all([ana, luc])
    await db_session.flush()
    db_session.add(
        NotificationPreference(clinic_id=test_clinic.id, patient_id=luc.id, preferred_locale="fr")
    )
    await db_session.commit()

    assert await _due_month_sent(db_session, test_clinic.id, ana.id) == "septiembre de 2026"
    assert await _due_month_sent(db_session, test_clinic.id, luc.id) == "septembre 2026"
