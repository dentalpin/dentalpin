"""Deducts inventory when a planned treatment is completed.

`treatment_plan.treatment_completed`'s payload carries the odontogram
Treatment *instance* id as `treatment_id` (see
treatment_plan/service.py `_finalize_item`). `TreatmentConsumable`
keys off the catalog item (`treatment_catalog_items.id`), not the
instance, so we resolve instance -> catalog item first via a raw SQL
lookup — this avoids importing odontogram's ORM model (and thus a
fourth module dependency) for one column.
"""

import logging
from uuid import UUID

from sqlalchemy import select, text

from app.database import async_session_maker
from app.modules.inventory.schemas import InventoryMovementCreate
from app.modules.inventory.service import InventoryService
from app.modules.treatment_consumables.models import TreatmentConsumable

logger = logging.getLogger(__name__)


async def _on_treatment_completed(payload: dict) -> None:
    clinic_id_raw = payload.get("clinic_id")
    treatment_id_raw = payload.get("treatment_id")
    if not clinic_id_raw or not treatment_id_raw:
        return

    clinic_id = UUID(str(clinic_id_raw))
    treatment_id = UUID(str(treatment_id_raw))
    completed_by_raw = payload.get("completed_by")
    created_by = UUID(str(completed_by_raw)) if completed_by_raw else None
    item_name = payload.get("item_name") or "treatment"

    async with async_session_maker() as db:
        catalog_row = (
            await db.execute(
                text("SELECT catalog_item_id FROM treatments WHERE id = :tid"),
                {"tid": treatment_id},
            )
        ).first()
        if catalog_row is None or catalog_row.catalog_item_id is None:
            return
        catalog_item_id = catalog_row.catalog_item_id

        consumables = (
            (
                await db.execute(
                    select(TreatmentConsumable).where(
                        TreatmentConsumable.clinic_id == clinic_id,
                        TreatmentConsumable.treatment_id == catalog_item_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        for consumable in consumables:
            try:
                await InventoryService.record_movement(
                    db,
                    clinic_id,
                    consumable.inventory_item_id,
                    InventoryMovementCreate(
                        reason="used",
                        quantity_delta=-consumable.quantity_needed,
                        reference=f"treatment:{treatment_id}",
                        notes=f"Auto-deducted — completed treatment: {item_name}",
                    ),
                    created_by,
                )
            except Exception:
                # One missing/insufficient item must not block the rest
                # of the consumables, or the completed-treatment flow
                # itself — event_bus.publish() already isolates handler
                # exceptions from the publisher, but a failed
                # record_movement leaves this session's transaction
                # aborted, so roll back before the next iteration.
                logger.exception(
                    "inventory_consumption: failed to deduct item %s for treatment %s",
                    consumable.inventory_item_id,
                    treatment_id,
                )
                await db.rollback()
