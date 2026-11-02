"""suppliers: happy-path CRUD + tenant isolation."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.suppliers.schemas import SupplierCreate, SupplierUpdate
from app.modules.suppliers.service import SupplierService
from app.modules.suppliers.tools import UpdateSupplierArgs, _update_supplier


@pytest.mark.asyncio
async def test_create_list_update_delete_happy_path(db_session: AsyncSession, test_clinic: Clinic):
    supplier = await SupplierService.create_supplier(
        db_session,
        test_clinic.id,
        SupplierCreate(
            name="Acme Dental Supplies",
            phone="555-0100",
            email="sales@acme.example.com",
            website="https://acme.example.com",
            payment_terms="NET30",
            lead_time_days=7,
            is_preferred=True,
        ),
    )
    contact, supplier_row = supplier
    assert contact.name == "Acme Dental Supplies"
    assert contact.contact_type == "supplier"
    assert contact.is_active is True
    assert supplier_row.website == "https://acme.example.com"
    assert supplier_row.payment_terms == "NET30"
    assert supplier_row.lead_time_days == 7
    assert supplier_row.is_preferred is True

    rows, total = await SupplierService.list_suppliers(db_session, test_clinic.id)
    assert total == 1
    assert rows[0][0].id == contact.id

    contact, supplier_row = await SupplierService.update_supplier(
        db_session,
        contact,
        supplier_row,
        SupplierUpdate(phone="555-0199", is_preferred=False),
    )
    assert contact.phone == "555-0199"
    assert contact.name == "Acme Dental Supplies"
    assert supplier_row.is_preferred is False
    assert supplier_row.payment_terms == "NET30"

    await SupplierService.delete_supplier(db_session, contact)

    rows, total = await SupplierService.list_suppliers(db_session, test_clinic.id)
    assert total == 0

    result = await SupplierService.get_supplier(db_session, test_clinic.id, contact.id)
    # Soft-delete keeps the row fetchable (historical purchase-order refs);
    # only list_suppliers (default) excludes inactive suppliers.
    assert result is not None
    deleted_contact, _ = result
    assert deleted_contact.is_active is False


@pytest.mark.asyncio
async def test_list_suppliers_filters_by_preferred(db_session: AsyncSession, test_clinic: Clinic):
    await SupplierService.create_supplier(
        db_session,
        test_clinic.id,
        SupplierCreate(name="Preferred Supplier", is_preferred=True),
    )
    await SupplierService.create_supplier(
        db_session,
        test_clinic.id,
        SupplierCreate(name="Regular Supplier", is_preferred=False),
    )

    rows, total = await SupplierService.list_suppliers(
        db_session, test_clinic.id, is_preferred=True
    )
    assert total == 1
    assert rows[0][0].name == "Preferred Supplier"

    rows, total = await SupplierService.list_suppliers(
        db_session, test_clinic.id, is_preferred=False
    )
    assert total == 1
    assert rows[0][0].name == "Regular Supplier"


@pytest.mark.asyncio
async def test_list_suppliers_search(db_session: AsyncSession, test_clinic: Clinic):
    await SupplierService.create_supplier(
        db_session,
        test_clinic.id,
        SupplierCreate(name="Acme Supplies", phone="555-0100"),
    )
    await SupplierService.create_supplier(
        db_session,
        test_clinic.id,
        SupplierCreate(name="Beta Supplies", email="beta@example.com"),
    )

    rows, total = await SupplierService.list_suppliers(db_session, test_clinic.id, search="Acme")
    assert total == 1
    assert rows[0][0].name == "Acme Supplies"

    rows, total = await SupplierService.list_suppliers(
        db_session, test_clinic.id, search="beta@example"
    )
    assert total == 1
    assert rows[0][0].name == "Beta Supplies"


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    contact, _ = await SupplierService.create_supplier(
        db_session,
        other_clinic.id,
        SupplierCreate(name="Other Clinic Supplier"),
    )

    rows, total = await SupplierService.list_suppliers(db_session, test_clinic.id)
    assert total == 0

    result = await SupplierService.get_supplier(db_session, test_clinic.id, contact.id)
    assert result is None


@pytest.mark.asyncio
async def test_update_tool_partial_update_keeps_other_fields(
    db_session: AsyncSession, test_clinic: Clinic
):
    contact, _ = await SupplierService.create_supplier(
        db_session,
        test_clinic.id,
        SupplierCreate(name="Acme", phone="555-0100", payment_terms="NET30"),
    )
    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id)
    out = await _update_supplier(
        ctx, UpdateSupplierArgs(supplier_id=str(contact.id), is_preferred=True)
    )
    assert "error" not in out
    assert out["name"] == "Acme"
    assert out["phone"] == "555-0100"
    assert out["payment_terms"] == "NET30"
    assert out["is_preferred"] is True


@pytest.mark.asyncio
async def test_cleared_lead_time_saves_as_empty(db_session: AsyncSession, test_clinic: Clinic):
    """A cleared lead-time input sends "" -- it means "unknown", not a 422 (#740)."""
    assert SupplierCreate(name="Acme", lead_time_days="").lead_time_days is None

    contact, supplier_row = await SupplierService.create_supplier(
        db_session, test_clinic.id, SupplierCreate(name="Acme", lead_time_days=7)
    )
    _, supplier_row = await SupplierService.update_supplier(
        db_session, contact, supplier_row, SupplierUpdate(lead_time_days="")
    )
    assert supplier_row.lead_time_days is None
