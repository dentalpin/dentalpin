"""lab_orders service tests, including tenant isolation."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.dates import clinic_today
from app.modules.contacts.models import Contact
from app.modules.lab_orders.schemas import LabOrderCreate, LabOrderUpdate
from app.modules.lab_orders.service import LabOrderService
from app.modules.patients.models import Patient


@pytest.mark.asyncio
async def test_create_list_and_receive_lab_order(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    contact = Contact(
        clinic_id=test_clinic.id, name="Dental Lab", contact_type="lab", is_active=True
    )
    db_session.add(contact)
    await db_session.commit()

    order = await LabOrderService.create_order(
        db_session,
        test_clinic.id,
        LabOrderCreate(
            patient_id=test_patient.id,
            lab_contact_id=contact.id,
            work_type="crown",
            sent_date=date(2026, 8, 22),
        ),
        None,
    )
    assert order.status == "sent"

    rows, total = await LabOrderService.list_order_responses(db_session, test_clinic.id)
    assert total == 1
    assert rows[0]["patient_id"] == test_patient.id
    assert rows[0]["lab_contact_name"] == "Dental Lab"

    # The service auto-stamps received_date with *today* when a payload
    # transitions to ``received`` without an explicit date — capture the
    # expected day before the call instead of hardcoding one (a hardcoded
    # date made this test fail everywhere but on its authoring day).
    expected_receipt = clinic_today(test_clinic.timezone)
    updated = await LabOrderService.update_order(
        db_session, test_clinic.id, order.id, LabOrderUpdate(status="received")
    )
    assert updated.status == "received"
    assert updated.received_date == expected_receipt

    # A repeated PATCH with status=received must not overwrite the
    # original receipt date (stamping happens only on the transition).
    original_receipt = date(2026, 8, 1)
    await LabOrderService.update_order(
        db_session, test_clinic.id, order.id, LabOrderUpdate(received_date=original_receipt)
    )
    re_received = await LabOrderService.update_order(
        db_session, test_clinic.id, order.id, LabOrderUpdate(status="received")
    )
    assert re_received.received_date == original_receipt


@pytest.mark.asyncio
async def test_lab_order_lookup_is_clinic_scoped(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    other_clinic = Clinic(
        id=uuid4(), name="Other Clinic", tax_id="B88888888", address={}, settings={}
    )
    db_session.add(other_clinic)
    other_patient = Patient(clinic_id=other_clinic.id, first_name="Other", last_name="Patient")
    other_contact = Contact(
        clinic_id=other_clinic.id, name="Other Lab", contact_type="lab", is_active=True
    )
    db_session.add_all([other_patient, other_contact])
    await db_session.commit()

    order = await LabOrderService.create_order(
        db_session,
        other_clinic.id,
        LabOrderCreate(
            patient_id=other_patient.id,
            lab_contact_id=other_contact.id,
            work_type="bridge",
            sent_date=date(2026, 8, 22),
        ),
        None,
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await LabOrderService.get_order(db_session, test_clinic.id, order.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_lab_must_be_a_lab_contact(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """A supplier, delegate or other contact is not a lab (#985).

    The create form only lists ``contact_type='lab'``, but the API and the
    ``create_lab_order`` copilot tool took any contact id, so an order could
    be "sent" to a supplier — the way purchase_orders refuses a non-supplier.
    """
    from fastapi import HTTPException

    lab = Contact(clinic_id=test_clinic.id, name="Lab", contact_type="lab", is_active=True)
    supplier = Contact(
        clinic_id=test_clinic.id, name="Depot", contact_type="supplier", is_active=True
    )
    db_session.add_all([lab, supplier])
    await db_session.commit()

    with pytest.raises(HTTPException) as created:
        await LabOrderService.create_order(
            db_session,
            test_clinic.id,
            LabOrderCreate(
                patient_id=test_patient.id,
                lab_contact_id=supplier.id,
                work_type="crown",
                sent_date=date(2026, 8, 22),
            ),
            None,
        )
    assert created.value.status_code == 400

    order = await LabOrderService.create_order(
        db_session,
        test_clinic.id,
        LabOrderCreate(
            patient_id=test_patient.id,
            lab_contact_id=lab.id,
            work_type="crown",
            sent_date=date(2026, 8, 22),
        ),
        None,
    )
    with pytest.raises(HTTPException) as moved:
        await LabOrderService.update_order(
            db_session, test_clinic.id, order.id, LabOrderUpdate(lab_contact_id=supplier.id)
        )
    assert moved.value.status_code == 400
