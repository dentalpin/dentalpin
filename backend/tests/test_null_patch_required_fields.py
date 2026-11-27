"""An explicit ``null`` on a required PUT/PATCH field is a 422 (#1151).

Same class as #976 and #1134: each field below is typed ``| None`` on its
``<X>Update`` schema while the column is NOT NULL. A ``null`` used to reach
the database and answer 500 (``NotNullViolationError``), a misleading 409
(billing series: every ``IntegrityError`` is mapped to the duplicate-prefix
message) or a ``TypeError`` 500 (payroll entry balance check). Each case
creates a row through the module, sends ``{field: null}`` and checks the
answer is a 422 naming the field and the stored value is unchanged.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.modules.billing.models import InvoiceSeries
from app.modules.gdpr.models import GdprRequest, RetentionPolicy
from app.modules.inventory.models import InventoryItem
from app.modules.leads.models import Lead
from app.modules.patients.models import Patient
from app.modules.patients_clinical.models import (
    Allergy,
    Medication,
    SurgicalHistory,
    SystemicDisease,
)
from app.modules.payroll.models import PayrollEntry, PayrollProfile
from app.modules.staff_tasks.models import StaffTask

A = "/api/v1"


def _data(response):
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


# Each setup creates one row and returns (method, url, row id).


async def _billing_series(c, h, db, clinic, patient):
    d = _data(
        await c.post(
            f"{A}/billing/series", headers=h, json={"prefix": "NUL", "series_type": "invoice"}
        )
    )
    return "PUT", f"{A}/billing/series/{d['id']}", d["id"]


async def _gdpr_request(c, h, db, clinic, patient):
    d = _data(
        await c.post(
            f"{A}/gdpr/requests",
            headers=h,
            json={
                "requester_name": "P",
                "requester_email": "p@example.com",
                "request_type": "access",
            },
        )
    )
    return "PATCH", f"{A}/gdpr/requests/{d['id']}", d["id"]


async def _gdpr_retention(c, h, db, clinic, patient):
    d = _data(
        await c.post(
            f"{A}/gdpr/retention",
            headers=h,
            json={"data_category": "null_probe", "retention_years": 5},
        )
    )
    return "PATCH", f"{A}/gdpr/retention/{d['id']}", d["id"]


async def _inventory_item(c, h, db, clinic, patient):
    d = _data(
        await c.post(
            f"{A}/inventory/",
            headers=h,
            json={"name": "Gloves", "stock_quantity": "5", "min_quantity": "1"},
        )
    )
    return "PATCH", f"{A}/inventory/{d['id']}", d["id"]


async def _lead(c, h, db, clinic, patient):
    d = _data(
        await c.post(
            f"{A}/leads/",
            headers=h,
            json={"full_name": "Lead", "phone": "+34600111222", "motive": "Cleaning"},
        )
    )["lead"]
    return "PATCH", f"{A}/leads/{d['id']}", d["id"]


async def _patient(c, h, db, clinic, patient):
    return "PUT", f"{A}/patients/{patient.id}", patient.id


def _clinical(kind, body):
    async def setup(c, h, db, clinic, patient):
        base = f"{A}/patients_clinical/patients/{patient.id}/{kind}"
        d = _data(await c.post(base, headers=h, json=body))
        return "PUT", f"{base}/{d['id']}", d["id"]

    return setup


async def _payroll_profile(c, h, db, clinic, patient):
    from tests.modules.payroll.test_payroll import _make_profile

    profile = await _make_profile(db, clinic.id)
    await db.commit()
    return "PATCH", f"{A}/payroll/profiles/{profile.id}", profile.id


async def _payroll_entry(c, h, db, clinic, patient):
    from tests.modules.payroll.test_payroll import _make_entry, _make_period, _make_user

    user = await _make_user(db, clinic.id)
    period = await _make_period(db, clinic.id)
    entry = await _make_entry(db, clinic.id, period.id, user.id)
    await db.commit()
    return "PATCH", f"{A}/payroll/entries/{entry.id}", entry.id


async def _staff_task(c, h, db, clinic, patient):
    d = _data(await c.post(f"{A}/staff_tasks/", headers=h, json={"title": "Task"}))
    return "PATCH", f"{A}/staff_tasks/{d['id']}", d["id"]


_allergy = _clinical("allergies", {"name": "Penicillin", "severity": "high"})
_medication = _clinical("medications", {"name": "Ibuprofen"})
_disease = _clinical(
    "systemic-diseases", {"name": "Diabetes", "is_controlled": True, "is_critical": True}
)
_surgery = _clinical("surgical-history", {"procedure": "Appendectomy"})

CASES = [
    (_billing_series, InvoiceSeries, ["reset_yearly", "is_default", "is_active"]),
    (_gdpr_request, GdprRequest, ["status"]),
    (_gdpr_retention, RetentionPolicy, ["retention_years", "is_active"]),
    (_inventory_item, InventoryItem, ["name", "category", "unit", "min_quantity", "is_active"]),
    (_lead, Lead, ["full_name", "phone", "motive", "status"]),
    (_patient, Patient, ["first_name", "last_name", "do_not_contact"]),
    (_allergy, Allergy, ["name", "severity"]),
    (_medication, Medication, ["name"]),
    (_disease, SystemicDisease, ["name", "is_controlled", "is_critical"]),
    (_surgery, SurgicalHistory, ["procedure"]),
    (_payroll_profile, PayrollProfile, ["payment_type", "currency", "is_active"]),
    (_payroll_entry, PayrollEntry, ["gross", "deductions"]),
    (_staff_task, StaffTask, ["title", "priority", "status"]),
]
PARAMS = [
    pytest.param(setup, model, field, id=f"{model.__name__}.{field}")
    for setup, model, fields in CASES
    for field in fields
]


async def _stored(model, row_id, field):
    # A fresh connection: the test client shares the fixture session, whose
    # identity map would hide what was (not) committed.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            q = select(getattr(model, field)).where(model.id == row_id)
            return (await conn.execute(q)).scalar_one()
    finally:
        await engine.dispose()


def test_case_count_matches_issue():
    assert len(PARAMS) == 33


@pytest.mark.asyncio
@pytest.mark.parametrize("setup,model,field", PARAMS)
async def test_null_on_required_field_is_422_and_row_untouched(
    setup, model, field, client, auth_headers, test_clinic, test_patient, db_session
):
    method, url, row_id = await setup(client, auth_headers, db_session, test_clinic, test_patient)
    await db_session.commit()
    before = await _stored(model, row_id, field)
    assert before is not None

    response = await client.request(method, url, headers=auth_headers, json={field: None})
    assert response.status_code == 422, response.text
    assert field in response.text

    await db_session.commit()
    assert await _stored(model, row_id, field) == before
