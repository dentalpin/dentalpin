"""Soft-delete semantics for patients_clinical (audit DATA-01).

House rule: never hard-delete patient data. Deletes archive the row
(``status = "archived"``); lists show only active rows; gets still return
the archived row for historical reference (M2); contact upserts revive.
"""

import pytest

from app.modules.patients_clinical.service import PatientsClinicalService

_KINDS = (
    ("allergy", {"name": "Penicilina", "severity": "critical"}),
    ("medication", {"name": "Ibuprofeno"}),
    ("disease", {"name": "Diabetes", "is_critical": True}),
    ("surgery", {"procedure": "Apendicectomia"}),
)


def _svc(kind):
    return {
        "allergy": (
            PatientsClinicalService.create_allergy,
            PatientsClinicalService.get_allergy,
            PatientsClinicalService.list_allergies,
            PatientsClinicalService.delete_allergy,
        ),
        "medication": (
            PatientsClinicalService.create_medication,
            PatientsClinicalService.get_medication,
            PatientsClinicalService.list_medications,
            PatientsClinicalService.delete_medication,
        ),
        "disease": (
            PatientsClinicalService.create_systemic_disease,
            PatientsClinicalService.get_systemic_disease,
            PatientsClinicalService.list_systemic_diseases,
            PatientsClinicalService.delete_systemic_disease,
        ),
        "surgery": (
            PatientsClinicalService.create_surgical_history,
            PatientsClinicalService.get_surgical_history,
            PatientsClinicalService.list_surgical_history,
            PatientsClinicalService.delete_surgical_history,
        ),
    }[kind]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,data", _KINDS, ids=[k for k, _ in _KINDS])
async def test_delete_archives_row_lists_exclude_get_returns(db_session, test_patient, kind, data):
    """Delete keeps the row (archived), hides it from lists, get still finds it."""
    create, get, list_all, delete = _svc(kind)
    row = await create(db_session, test_patient.clinic_id, test_patient.id, dict(data))
    row_id = row.id
    assert row.status == "active"

    fetched = await get(db_session, row_id)
    assert fetched is not None
    await delete(db_session, fetched)

    assert (await get(db_session, row_id)) is not None
    assert (await get(db_session, row_id)).status == "archived"
    remaining = await list_all(db_session, test_patient.id)
    assert all(r.id != row_id for r in remaining)


@pytest.mark.asyncio
async def test_archived_allergy_stops_alerting(db_session, test_patient):
    """Alerts derive from the active set: an archived critical allergy is silent."""
    row = await PatientsClinicalService.create_allergy(
        db_session,
        test_patient.clinic_id,
        test_patient.id,
        {"name": "Penicilina", "severity": "critical"},
    )
    assert any(
        a["type"] == "allergy"
        for a in await PatientsClinicalService.compute_alerts(db_session, test_patient.id)
    )

    await PatientsClinicalService.delete_allergy(db_session, row)
    assert not any(
        a["type"] == "allergy"
        for a in await PatientsClinicalService.compute_alerts(db_session, test_patient.id)
    )


@pytest.mark.asyncio
async def test_contact_upsert_revives_archived_row(db_session, test_patient):
    """1:1 contacts reuse the PK row: delete then upsert reactivates it."""
    contact = await PatientsClinicalService.upsert_emergency_contact(
        db_session,
        test_patient.clinic_id,
        test_patient.id,
        {"name": "Ana", "phone": "+34111111"},
    )
    await PatientsClinicalService.delete_emergency_contact(db_session, contact)
    assert (
        await PatientsClinicalService.get_emergency_contact(db_session, test_patient.id)
    ).status == "archived"

    revived = await PatientsClinicalService.upsert_emergency_contact(
        db_session,
        test_patient.clinic_id,
        test_patient.id,
        {"name": "Ana", "phone": "+34222222"},
    )
    assert revived.status == "active"
    assert revived.phone == "+34222222"


@pytest.mark.asyncio
async def test_replace_preserves_history(db_session, test_patient):
    """Bulk replace archives the old set instead of destroying it."""
    old_row = await PatientsClinicalService.create_allergy(
        db_session,
        test_patient.clinic_id,
        test_patient.id,
        {"name": "Penicilina", "severity": "high"},
    )
    await PatientsClinicalService.replace_medical_history(
        db_session,
        test_patient.clinic_id,
        test_patient.id,
        {"allergies": [{"name": "Latex", "severity": "medium"}]},
        None,
    )
    current = await PatientsClinicalService.list_allergies(db_session, test_patient.id)
    assert [a.name for a in current] == ["Latex"]
    # The superseded row survives, archived, instead of being destroyed.
    kept = await PatientsClinicalService.get_allergy(db_session, old_row.id)
    assert kept is not None and kept.status == "archived" and kept.name == "Penicilina"
