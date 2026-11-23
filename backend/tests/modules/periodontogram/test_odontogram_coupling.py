"""Periodontogram draft pre-fill from the odontogram module."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.odontogram.models import (
    ToothRecord,
    Treatment,
    TreatmentTooth,
)
from app.modules.patients.models import Patient

pytestmark = pytest.mark.asyncio


async def _open_draft(client: AsyncClient, headers: dict[str, str], patient_id: str) -> dict:
    response = await client.post(
        f"/api/v1/periodontogram/patients/{patient_id}/draft",
        headers=headers,
    )
    return response.json()["data"]


async def test_missing_tooth_in_odontogram_marks_perio_tooth_absent(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
    db_session,
) -> None:
    db_session.add(
        ToothRecord(
            id=uuid4(),
            clinic_id=test_patient.clinic_id,
            patient_id=test_patient.id,
            tooth_number=46,
            tooth_type="permanent",
            general_condition="missing",
            surfaces={},
            is_displaced=False,
            is_rotated=False,
        )
    )
    await db_session.commit()

    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    tooth = next(t for t in draft["teeth"] if t["tooth_number"] == 46)
    assert tooth["is_present"] is False
    assert tooth["is_implant"] is False


async def test_performed_implant_marks_perio_tooth_as_implant(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
    db_session,
) -> None:
    # Tooth record (required so TreatmentTooth FK resolves).
    record = ToothRecord(
        id=uuid4(),
        clinic_id=test_patient.clinic_id,
        patient_id=test_patient.id,
        tooth_number=14,
        tooth_type="permanent",
        general_condition="implant",
        surfaces={},
        is_displaced=False,
        is_rotated=False,
    )
    db_session.add(record)
    await db_session.flush()

    treatment = Treatment(
        id=uuid4(),
        clinic_id=test_patient.clinic_id,
        patient_id=test_patient.id,
        clinical_type="implant",
        scope="tooth",
        status="performed",
        recorded_at=datetime.now(UTC),
        performed_at=datetime.now(UTC),
        source_module="test",
    )
    db_session.add(treatment)
    await db_session.flush()

    db_session.add(
        TreatmentTooth(
            id=uuid4(),
            treatment_id=treatment.id,
            tooth_record_id=record.id,
            tooth_number=14,
        )
    )
    await db_session.commit()

    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    tooth = next(t for t in draft["teeth"] if t["tooth_number"] == 14)
    assert tooth["is_implant"] is True
    assert tooth["is_present"] is True


async def test_patient_without_odontogram_data_uses_defaults(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
) -> None:
    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    for tooth in draft["teeth"]:
        assert tooth["is_present"] is True
        assert tooth["is_implant"] is False


async def test_close_snapshot_freezes_indices_and_serves_endpoint(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
) -> None:
    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    snapshot_id = draft["id"]

    # Populate one site with deep probing depth + bleeding.
    await client.patch(
        f"/api/v1/periodontogram/snapshots/{snapshot_id}/teeth/11/sites/V",
        headers=auth_headers,
        json={
            "probing_depth_mm": 6,
            "gingival_margin_mm": 1,
            "bleeding_on_probing": True,
            "plaque": True,
        },
    )

    close = await client.post(
        f"/api/v1/periodontogram/snapshots/{snapshot_id}/close",
        headers=auth_headers,
        json={},
    )
    assert close.status_code == 200, close.text
    indices = close.json()["data"]["indices"]
    # Denominator is the theoretical site count (32 present teeth × 6 = 192),
    # so a single bleeder / plaque site reads as 1/192 = 0.52%, not 100%.
    # See ``indices.py`` — unmeasured sites count as zero, not excluded.
    assert indices["bop_pct"] == round(100.0 / 192, 2)
    assert indices["pi_pct"] == round(100.0 / 192, 2)
    assert indices["cal_mean_mm"] == round(7 / 192, 2)
    assert indices["deep_pockets_count"] == 1

    # /indices endpoint returns the frozen indices on a closed snapshot.
    indices_response = await client.get(
        f"/api/v1/periodontogram/snapshots/{snapshot_id}/indices",
        headers=auth_headers,
    )
    assert indices_response.status_code == 200
    assert indices_response.json()["data"] == indices


async def _add_treatment(
    db_session,
    patient: Patient,
    tooth_number: int,
    clinical_type: str,
    status: str = "performed",
    deleted: bool = False,
) -> None:
    record = (
        await db_session.execute(
            select(ToothRecord).where(
                ToothRecord.patient_id == patient.id,
                ToothRecord.tooth_number == tooth_number,
            )
        )
    ).scalar_one_or_none()
    if record is None:
        record = ToothRecord(
            id=uuid4(),
            clinic_id=patient.clinic_id,
            patient_id=patient.id,
            tooth_number=tooth_number,
            tooth_type="permanent",
            general_condition="healthy",
            surfaces={},
            is_displaced=False,
            is_rotated=False,
        )
        db_session.add(record)
        await db_session.flush()
    now = datetime.now(UTC)
    treatment = Treatment(
        id=uuid4(),
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        clinical_type=clinical_type,
        scope="tooth",
        status=status,
        recorded_at=now,
        performed_at=now if status == "performed" else None,
        source_module="odontogram",
        deleted_at=now if deleted else None,
    )
    db_session.add(treatment)
    await db_session.flush()
    db_session.add(
        TreatmentTooth(
            id=uuid4(),
            treatment_id=treatment.id,
            tooth_record_id=record.id,
            tooth_number=tooth_number,
        )
    )
    await db_session.commit()


async def test_missing_treatment_and_performed_extraction_mark_tooth_absent(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
    db_session,
) -> None:
    """#1091: the odontogram UI records a missing tooth as a ``missing``
    treatment (ToothRecord.general_condition stays ``healthy``), and an
    extraction as a performed ``extraction`` treatment. Both are absent."""
    await _add_treatment(db_session, test_patient, 36, "missing")
    await _add_treatment(db_session, test_patient, 47, "extraction")
    # Not absent: planned extraction, soft-deleted missing finding.
    await _add_treatment(db_session, test_patient, 17, "extraction", status="planned")
    await _add_treatment(db_session, test_patient, 27, "missing", deleted=True)

    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    by_tn = {t["tooth_number"]: t for t in draft["teeth"]}
    assert by_tn[36]["is_present"] is False
    assert by_tn[47]["is_present"] is False
    assert by_tn[17]["is_present"] is True
    assert by_tn[27]["is_present"] is True


async def test_implant_after_extraction_stays_present_as_implant(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
    db_session,
) -> None:
    await _add_treatment(db_session, test_patient, 25, "extraction")
    await _add_treatment(db_session, test_patient, 25, "implant")

    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    tooth = next(t for t in draft["teeth"] if t["tooth_number"] == 25)
    assert tooth["is_present"] is True
    assert tooth["is_implant"] is True


async def test_missing_treatment_shrinks_index_denominator(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_patient: Patient,
    db_session,
) -> None:
    await _add_treatment(db_session, test_patient, 46, "missing")
    draft = await _open_draft(client, auth_headers, str(test_patient.id))
    snapshot_id = draft["id"]
    await client.patch(
        f"/api/v1/periodontogram/snapshots/{snapshot_id}/teeth/11/sites/V",
        headers=auth_headers,
        json={"probing_depth_mm": 4, "gingival_margin_mm": 0, "bleeding_on_probing": True},
    )
    close = await client.post(
        f"/api/v1/periodontogram/snapshots/{snapshot_id}/close",
        headers=auth_headers,
        json={},
    )
    assert close.status_code == 200, close.text
    # 31 present teeth × 6 sites = 186.
    assert close.json()["data"]["indices"]["bop_pct"] == round(100.0 / 186, 2)
