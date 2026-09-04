"""supplier_items: happy-path CRUD, duplicate guard, tenant isolation, soft delete."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.contacts.models import Contact
from app.modules.inventory.schemas import InventoryItemCreate
from app.modules.inventory.service import InventoryService
from app.modules.supplier_items.schemas import SupplierItemCreate, SupplierItemUpdate
from app.modules.supplier_items.service import SupplierItemService
from app.modules.suppliers.schemas import SupplierCreate
from app.modules.suppliers.service import SupplierService


async def _make_supplier(db: AsyncSession, clinic_id, *, name="Acme Supplies") -> tuple:
    return await SupplierService.create_supplier(
        db, clinic_id, SupplierCreate(name=name, payment_terms="NET30", lead_time_days=5)
    )


async def _make_item(db: AsyncSession, clinic_id, *, name="Composite A2") -> object:
    return await InventoryService.create_item(
        db,
        clinic_id,
        InventoryItemCreate(name=name, category="consumables", unit_cost=Decimal("12.50")),
        created_by=None,
    )


@pytest.mark.asyncio
async def test_create_list_update_deactivate_happy_path(
    db_session: AsyncSession, test_clinic: Clinic
):
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)

    link, sname, iname = await SupplierItemService.create_link(
        db_session,
        test_clinic.id,
        SupplierItemCreate(
            supplier_id=supplier.id,
            inventory_item_id=item.id,
            supplier_sku="ACME-COMPOSITE-A2",
            price=Decimal("9.99"),
        ),
    )
    assert sname == "Acme Supplies"
    assert iname == "Composite A2"
    assert link.supplier_sku == "ACME-COMPOSITE-A2"
    assert link.price == Decimal("9.99")
    assert link.is_active is True

    fetched = await SupplierItemService.get_link(db_session, test_clinic.id, link.id)
    assert fetched is not None
    assert fetched[0].id == link.id
    assert fetched[1:] == ("Acme Supplies", "Composite A2")

    rows, total = await SupplierItemService.list_links(db_session, test_clinic.id)
    assert total == 1
    assert rows[0][1].name == "Acme Supplies"
    assert rows[0][2].name == "Composite A2"

    link = await SupplierItemService.update_link(
        db_session,
        link,
        SupplierItemUpdate(price=Decimal("7.50")),
    )
    assert link.supplier_sku == "ACME-COMPOSITE-A2"  # omitted SKU not wiped (M4)
    assert link.price == Decimal("7.50")

    # Soft delete (L7): row is kept, marked inactive, filtered from list/get.
    await SupplierItemService.deactivate_link(db_session, link)

    link = await SupplierItemService.get_link(db_session, test_clinic.id, link.id)
    assert link is None  # inactive rows are not returned by get

    rows, total = await SupplierItemService.list_links(db_session, test_clinic.id)
    assert total == 0  # inactive rows are not returned by list


@pytest.mark.asyncio
async def test_deactivated_link_is_soft_delete_not_hard(
    db_session: AsyncSession, test_clinic: Clinic
):
    """L7 semantics: get_link filters inactive rows, yet the row is kept at
    the DB level (soft, not hard DELETE)."""
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)
    link, _, _ = await SupplierItemService.create_link(
        db_session,
        test_clinic.id,
        SupplierItemCreate(supplier_id=supplier.id, inventory_item_id=item.id),
    )

    await SupplierItemService.deactivate_link(db_session, link)
    assert (
        await SupplierItemService.get_link(db_session, test_clinic.id, link.id) is None
    )  # get_link filters inactive rows

    # The row must still exist at the DB level (soft, not hard DELETE).
    from sqlalchemy import select

    from app.modules.supplier_items.models import SupplierItem

    row = (
        await db_session.execute(select(SupplierItem).where(SupplierItem.id == link.id))
    ).scalar_one()
    assert row.is_active is False


@pytest.mark.asyncio
async def test_create_duplicate_supplier_item_is_conflict(
    db_session: AsyncSession, test_clinic: Clinic
):
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)

    await SupplierItemService.create_link(
        db_session,
        test_clinic.id,
        SupplierItemCreate(supplier_id=supplier.id, inventory_item_id=item.id),
    )

    with pytest.raises(HTTPException) as exc:
        await SupplierItemService.create_link(
            db_session,
            test_clinic.id,
            SupplierItemCreate(
                supplier_id=supplier.id, inventory_item_id=item.id, price=Decimal("8.00")
            ),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_create_validates_ends_in_clinic(db_session: AsyncSession, test_clinic: Clinic):
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    _, supplier = await _make_supplier(db_session, other_clinic.id, name="Other Supplier")
    item = await _make_item(db_session, other_clinic.id, name="Other Item")

    # Foreign supplier is not visible in test_clinic -> 404.
    with pytest.raises(HTTPException) as exc:
        await SupplierItemService.create_link(
            db_session,
            test_clinic.id,
            SupplierItemCreate(supplier_id=supplier.id, inventory_item_id=item.id),
        )
    assert exc.value.status_code == 404

    # In-clinic supplier, foreign item -> 404.
    _, my_supplier = await _make_supplier(db_session, test_clinic.id)
    with pytest.raises(HTTPException) as exc:
        await SupplierItemService.create_link(
            db_session,
            test_clinic.id,
            SupplierItemCreate(supplier_id=my_supplier.id, inventory_item_id=item.id),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_filters_by_supplier_and_item(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier_a = await _make_supplier(db_session, test_clinic.id, name="Acme Supplies")
    _, supplier_b = await _make_supplier(db_session, test_clinic.id, name="Beta Supplies")
    item_a = await _make_item(db_session, test_clinic.id, name="Gloves")
    item_b = await _make_item(db_session, test_clinic.id, name="Masks")

    pairs = [
        (supplier_a.id, item_a.id),
        (supplier_a.id, item_b.id),
        (supplier_b.id, item_a.id),
    ]
    for sid, iid in pairs:
        await SupplierItemService.create_link(
            db_session, test_clinic.id, SupplierItemCreate(supplier_id=sid, inventory_item_id=iid)
        )

    rows, total = await SupplierItemService.list_links(
        db_session, test_clinic.id, supplier_id=supplier_a.id
    )
    assert total == 2

    rows, total = await SupplierItemService.list_links(
        db_session, test_clinic.id, inventory_item_id=item_a.id
    )
    assert total == 2

    rows, total = await SupplierItemService.list_links(
        db_session,
        test_clinic.id,
        supplier_id=supplier_b.id,
        inventory_item_id=item_a.id,
    )
    assert total == 1


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

    _, supplier = await _make_supplier(db_session, other_clinic.id, name="Other Supplier")
    item = await _make_item(db_session, other_clinic.id, name="Other Item")

    link, _, _ = await SupplierItemService.create_link(
        db_session,
        other_clinic.id,
        SupplierItemCreate(supplier_id=supplier.id, inventory_item_id=item.id),
    )

    rows, total = await SupplierItemService.list_links(db_session, test_clinic.id)
    assert total == 0

    result = await SupplierItemService.get_link(db_session, test_clinic.id, link.id)
    assert result is None


@pytest.mark.asyncio
async def test_relink_after_deactivate_revives_row(db_session: AsyncSession, test_clinic: Clinic):
    """Soft delete must not lock the (supplier, item) pair behind the UNIQUE."""
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)
    link, _, _ = await SupplierItemService.create_link(
        db_session,
        test_clinic.id,
        SupplierItemCreate(supplier_id=supplier.id, inventory_item_id=item.id, price=Decimal("1")),
    )
    await SupplierItemService.deactivate_link(db_session, link)

    revived, _, _ = await SupplierItemService.create_link(
        db_session,
        test_clinic.id,
        SupplierItemCreate(
            supplier_id=supplier.id,
            inventory_item_id=item.id,
            supplier_sku="NEW",
            price=Decimal("2"),
        ),
    )
    assert revived.id == link.id  # same row, revived
    assert revived.is_active is True
    assert revived.supplier_sku == "NEW"
    assert revived.price == Decimal("2")
    _, total = await SupplierItemService.list_links(db_session, test_clinic.id)
    assert total == 1


@pytest.mark.asyncio
async def test_create_rejects_contact_without_supplier_row(
    db_session: AsyncSession, test_clinic: Clinic
):
    """A Contact(type='supplier') with no suppliers row is not a valid FK target -> 404."""
    contact = Contact(clinic_id=test_clinic.id, name="Bare contact", contact_type="supplier")
    db_session.add(contact)
    await db_session.commit()
    item = await _make_item(db_session, test_clinic.id)

    with pytest.raises(HTTPException) as exc:
        await SupplierItemService.create_link(
            db_session,
            test_clinic.id,
            SupplierItemCreate(supplier_id=contact.id, inventory_item_id=item.id),
        )
    assert exc.value.status_code == 404
