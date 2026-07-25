import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.inventory.models import InventoryItem

from .models import TreatmentConsumable


class TreatmentNotFoundError(Exception):
    pass


class InventoryItemNotFoundError(Exception):
    pass


class DuplicateLinkError(Exception):
    pass


async def _assert_treatment_exists(
    db: AsyncSession, *, clinic_id: uuid.UUID, treatment_id: uuid.UUID
) -> None:
    stmt = select(TreatmentCatalogItem.id).where(
        TreatmentCatalogItem.id == treatment_id,
        TreatmentCatalogItem.clinic_id == clinic_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise TreatmentNotFoundError(str(treatment_id))


async def _assert_inventory_item_exists(
    db: AsyncSession, *, clinic_id: uuid.UUID, inventory_item_id: uuid.UUID
) -> None:
    stmt = select(InventoryItem.id).where(
        InventoryItem.id == inventory_item_id,
        InventoryItem.clinic_id == clinic_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise InventoryItemNotFoundError(str(inventory_item_id))


async def create_link(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    treatment_id: uuid.UUID,
    inventory_item_id: uuid.UUID,
    quantity_needed: Decimal,
) -> TreatmentConsumable:
    await _assert_treatment_exists(db, clinic_id=clinic_id, treatment_id=treatment_id)
    await _assert_inventory_item_exists(
        db, clinic_id=clinic_id, inventory_item_id=inventory_item_id
    )

    link = TreatmentConsumable(
        clinic_id=clinic_id,
        treatment_id=treatment_id,
        inventory_item_id=inventory_item_id,
        quantity_needed=quantity_needed,
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateLinkError(
            f"{treatment_id}:{inventory_item_id}"
        ) from exc
    await db.refresh(link)
    return link


async def update_link(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    link_id: uuid.UUID,
    quantity_needed: Decimal,
) -> TreatmentConsumable | None:
    stmt = select(TreatmentConsumable).where(
        TreatmentConsumable.id == link_id, TreatmentConsumable.clinic_id == clinic_id
    )
    link = (await db.execute(stmt)).scalar_one_or_none()
    if link is None:
        return None
    link.quantity_needed = quantity_needed
    await db.commit()
    await db.refresh(link)
    return link


async def delete_link(
    db: AsyncSession, *, clinic_id: uuid.UUID, link_id: uuid.UUID
) -> bool:
    stmt = select(TreatmentConsumable).where(
        TreatmentConsumable.id == link_id, TreatmentConsumable.clinic_id == clinic_id
    )
    link = (await db.execute(stmt)).scalar_one_or_none()
    if link is None:
        return False
    await db.delete(link)
    await db.commit()
    return True


async def get_link(
    db: AsyncSession, *, clinic_id: uuid.UUID, link_id: uuid.UUID
) -> TreatmentConsumable | None:
    stmt = select(TreatmentConsumable).where(
        TreatmentConsumable.id == link_id, TreatmentConsumable.clinic_id == clinic_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_links(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    treatment_id: uuid.UUID | None = None,
    inventory_item_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TreatmentConsumable], int]:
    from sqlalchemy import func

    stmt = select(TreatmentConsumable).where(TreatmentConsumable.clinic_id == clinic_id)
    if treatment_id is not None:
        stmt = stmt.where(TreatmentConsumable.treatment_id == treatment_id)
    if inventory_item_id is not None:
        stmt = stmt.where(TreatmentConsumable.inventory_item_id == inventory_item_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = stmt.order_by(TreatmentConsumable.created_at.desc()).limit(page_size).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total
