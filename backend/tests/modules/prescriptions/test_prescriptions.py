"""prescriptions: lifecycle, templates, prescriber snapshot, tenancy, HTTP codes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.patients.models import Patient
from app.modules.prescriptions.service import PrescriptionService


async def _patient(db_session, clinic_id):
    p = Patient(clinic_id=clinic_id, first_name="Rx", last_name="Taker")
    db_session.add(p)
    await db_session.commit()
    return p


async def _prescriber(db_session, clinic_id):
    user = User(
        id=uuid4(),
        email=f"rx-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Doc",
        last_name="Tor",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role="dentist")
    )
    await db_session.commit()
    return user


def _items():
    return [
        {
            "medication_name": "Amoxicilina",
            "dosage": "500 mg",
            "frequency": "8h",
            "duration": "7 days",
        },
        {"medication_name": "Ibuprofeno", "dosage": "400 mg", "frequency": "8h"},
    ]


@pytest.mark.asyncio
async def test_draft_issue_cancel_lifecycle(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    doc = await _prescriber(db_session, test_clinic.id)
    row = await PrescriptionService.create_draft(
        db_session,
        test_clinic.id,
        doc.id,
        test_patient.id,
        notes="n",
        locale="es",
        items=_items(),
    )
    await db_session.commit()
    assert row.status == "draft"

    issued = await PrescriptionService.issue(db_session, test_clinic.id, row.id, doc.id)
    await db_session.commit()
    assert issued.status == "issued"
    assert issued.issued_at is not None

    # Issued rows freeze.
    with pytest.raises(HTTPException) as exc:
        await PrescriptionService.update_draft(db_session, test_clinic.id, row.id, {"notes": "x"})
    assert exc.value.status_code == 422

    cancelled = await PrescriptionService.cancel(db_session, test_clinic.id, row.id)
    await db_session.commit()
    assert cancelled.status == "cancelled"
    with pytest.raises(HTTPException) as exc2:
        await PrescriptionService.cancel(db_session, test_clinic.id, row.id)
    assert exc2.value.status_code == 409


@pytest.mark.asyncio
async def test_issue_empty_is_422(db_session: AsyncSession, test_clinic: Clinic):
    patient = await _patient(db_session, test_clinic.id)
    row = await PrescriptionService.create_draft(
        db_session,
        test_clinic.id,
        (await _prescriber(db_session, test_clinic.id)).id,
        patient.id,
        notes=None,
        locale="es",
        items=[],
    )
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await PrescriptionService.issue(
            db_session, test_clinic.id, row.id, (await _prescriber(db_session, test_clinic.id)).id
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_update_replaces_items(db_session: AsyncSession, test_clinic: Clinic):
    patient = await _patient(db_session, test_clinic.id)
    row = await PrescriptionService.create_draft(
        db_session,
        test_clinic.id,
        (await _prescriber(db_session, test_clinic.id)).id,
        patient.id,
        notes=None,
        locale="es",
        items=_items(),
    )
    await db_session.commit()
    updated = await PrescriptionService.update_draft(
        db_session, test_clinic.id, row.id, {"items": [_items()[0]]}
    )
    await db_session.commit()
    items = await PrescriptionService._items(db_session, test_clinic.id, row.id)
    assert len(items) == 1 and items[0].medication_name == "Amoxicilina"
    assert updated.notes is None  # exclude_unset: untouched stays


@pytest.mark.asyncio
async def test_templates_crud_and_409(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id  # capture: later rollbacks expire fixtures (#188)
    tpl = await PrescriptionService.create_template(
        db_session, clinic_id, "post-extraction", _items()
    )
    assert tpl.items[0]["medication_name"] == "Amoxicilina"
    tpl_id = tpl.id
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await PrescriptionService.create_template(db_session, clinic_id, "post-extraction", [])
    assert exc.value.status_code == 409
    renamed = await PrescriptionService.update_template(
        db_session, clinic_id, tpl_id, {"name": "post-exo"}
    )
    await db_session.commit()
    await db_session.refresh(renamed)
    assert renamed.name == "post-exo"
    await PrescriptionService.delete_template(db_session, clinic_id, tpl_id)
    await db_session.commit()
    assert await PrescriptionService.list_templates(db_session, clinic_id) == []


@pytest.mark.asyncio
async def test_foreign_clinic_is_invisible(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    row = await PrescriptionService.create_draft(
        db_session,
        test_clinic.id,
        (await _prescriber(db_session, test_clinic.id)).id,
        test_patient.id,
        notes=None,
        locale="es",
        items=[],
    )
    await db_session.commit()
    other = Clinic(id=uuid4(), name="Other", tax_id="B9", address={}, settings={})
    db_session.add(other)
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await PrescriptionService.issue(db_session, other.id, row.id, uuid4())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_warnings_shape(db_session: AsyncSession, test_clinic: Clinic):
    patient = await _patient(db_session, test_clinic.id)
    warnings = await PrescriptionService.prescribe_warnings(db_session, test_clinic.id, patient.id)
    assert set(warnings) == {"allergies", "interaction_flags"}
    assert all(isinstance(v, str) for v in warnings["allergies"])


@pytest.mark.asyncio
async def test_http_codes(client, auth_headers, test_clinic: Clinic, test_patient: Patient):
    pid = str(test_patient.id)
    created = await client.post(
        f"/api/v1/prescriptions/patients/{pid}/prescriptions",
        json={"patient_id": pid, "items": _items()},
        headers=auth_headers,
    )
    assert created.status_code == 201
    rx_id = created.json()["data"]["id"]

    mismatch = await client.post(
        f"/api/v1/prescriptions/patients/{uuid4()}/prescriptions",
        json={"patient_id": pid, "items": []},
        headers=auth_headers,
    )
    assert mismatch.status_code == 422

    patched = await client.patch(
        f"/api/v1/prescriptions/prescriptions/{rx_id}",
        json={"notes": "take with food"},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["notes"] == "take with food"

    issued = await client.post(
        f"/api/v1/prescriptions/prescriptions/{rx_id}/issue", headers=auth_headers
    )
    assert issued.status_code == 200
    assert issued.json()["data"]["status"] == "issued"

    frozen = await client.patch(
        f"/api/v1/prescriptions/prescriptions/{rx_id}",
        json={"notes": "late edit"},
        headers=auth_headers,
    )
    assert frozen.status_code == 422

    cancelled = await client.post(
        f"/api/v1/prescriptions/prescriptions/{rx_id}/cancel", headers=auth_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"

    warned = await client.get(
        f"/api/v1/prescriptions/patients/{pid}/prescribe-warnings", headers=auth_headers
    )
    assert warned.status_code == 200
    assert set(warned.json()["data"]) == {"allergies", "interaction_flags"}

    tpl = await client.post(
        "/api/v1/prescriptions/templates",
        json={"name": "t", "items": _items()},
        headers=auth_headers,
    )
    assert tpl.status_code == 201
    tpl_id = tpl.json()["data"]["id"]
    dropped = await client.delete(f"/api/v1/prescriptions/templates/{tpl_id}", headers=auth_headers)
    assert dropped.status_code == 204


@pytest.mark.asyncio
async def test_archived_allergies_excluded_from_warnings(
    db_session: AsyncSession, test_clinic: Clinic
):
    from app.modules.patients_clinical.models import Allergy

    patient = await _patient(db_session, test_clinic.id)
    db_session.add(Allergy(clinic_id=test_clinic.id, patient_id=patient.id, name="Penicilina"))
    db_session.add(
        Allergy(
            clinic_id=test_clinic.id,
            patient_id=patient.id,
            name="Aspirina",
            status="archived",
        )
    )
    await db_session.commit()
    warnings = await PrescriptionService.prescribe_warnings(db_session, test_clinic.id, patient.id)
    assert "Penicilina" in warnings["allergies"]
    assert "Aspirina" not in warnings["allergies"]


def test_flag_format_is_readable():
    from types import SimpleNamespace

    flag = SimpleNamespace(
        type="interaction",
        risk_note="Riesgo de sangrado",
        involved=["Warfarina", "Ibuprofeno"],
    )
    assert PrescriptionService._format_flag(flag) == "Warfarina + Ibuprofeno: Riesgo de sangrado"


def test_pdf_labels_follow_locale_and_marks_non_issued():
    from types import SimpleNamespace

    from app.modules.prescriptions.pdf import build_pdf_data, render_html

    clinic = {
        "name": "Clinica",
        "address": {
            "street": "Calle Mayor 1",
            "postal_code": "28001",
            "city": "Madrid",
            "country": "ES",
        },
    }
    draft = SimpleNamespace(
        status="draft",
        issued_at=None,
        prescriber_name="Doc",
        license_number=None,
        notes=None,
    )
    data = build_pdf_data(draft, [], "Pac", clinic, locale="es")
    assert data["labels"]["date"] == "Fecha"
    assert data["labels"]["patient"] == "Paciente"
    assert data["status_mark"] == "BORRADOR"
    assert "Calle Mayor 1" in data["clinic_address"]
    assert "Madrid" in data["clinic_address"]
    html = render_html(data)
    assert "BORRADOR" in html
    assert "Fecha:" in html
    assert "Receta médica" in html
    assert "Firma:" in html
    assert "Notas:" not in html  # empty notes leave no row

    issued = SimpleNamespace(
        status="issued",
        issued_at=None,
        prescriber_name="Doc",
        license_number="123",
        notes=None,
    )
    data_en = build_pdf_data(issued, [], "Pat", clinic, locale="en")
    assert data_en["labels"]["date"] == "Date"
    assert "DRAFT" not in render_html(data_en)
    assert "CANCELLED" not in render_html(data_en)
    assert "Prescription" in render_html(data_en)
    assert "Signature:" in render_html(data_en)


@pytest.mark.asyncio
async def test_create_stores_locale_and_route(
    client, auth_headers, test_clinic: Clinic, test_patient: Patient
):
    pid = str(test_patient.id)
    created = await client.post(
        f"/api/v1/prescriptions/patients/{pid}/prescriptions",
        json={
            "patient_id": pid,
            "locale": "pt",
            "items": [{"medication_name": "Amoxicilina", "route": "oral"}],
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["data"]["locale"] == "pt"
    assert created.json()["data"]["items"][0]["route"] == "oral"


def test_pdf_every_locale_set_is_complete():
    """Every label set carries the same keys, so no locale can 500 on a
    caption that only es/en define (title/signature/date_format)."""
    from types import SimpleNamespace

    from app.modules.prescriptions.pdf import _get_labels, build_pdf_data, render_html

    rx = SimpleNamespace(
        status="issued",
        issued_at=datetime(2026, 9, 22, tzinfo=UTC),
        prescriber_name="Doc",
        license_number="123",
        notes=None,
    )
    expected = set(_get_labels("en"))
    for locale in ("es", "en", "fr", "pt", "de", "hu", "pl", "it", "ar", "ta"):
        assert set(_get_labels(locale)) == expected, locale
        html = render_html(build_pdf_data(rx, [], "Pat", {"name": "C"}, locale=locale))
        assert f'lang="{locale}"' in html
