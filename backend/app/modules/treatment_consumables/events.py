"""treatment_consumables event handlers — subscription inversion (#226).

``odontogram.treatment.performed`` → read the treatment_consumables links
for the performed catalog item via ORM and call
``InventoryService.deduct_for_treatment`` (a clean public primitive on
inventory).  No raw SQL, no inspector guard, no fail-soft branch.

This module already depends on inventory (declared in manifest), so
the subscription direction is legal and creates no cycle.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)

# Payload keys checked for actor attribution on the deduction ledger
# rows (same approach as activity_journal's _ACTOR_KEYS).
_ACTOR_KEYS = ("performed_by", "changed_by", "user_id")


async def on_treatment_performed(data: dict, db) -> None:
    clinic_raw = data.get("clinic_id")
    catalog_raw = data.get("catalog_item_id")
    if not clinic_raw or not catalog_raw:
        return  # treatment without a catalog link — nothing to deduct

    try:
        clinic_id = UUID(str(clinic_raw))
        catalog_item_id = UUID(str(catalog_raw))
    except (ValueError, TypeError):
        logger.warning(
            "treatment_consumables: malformed ids in treatment.performed — skipped"
        )
        return

    from app.modules.inventory.service import InventoryService

    actor_id = None
    for key in _ACTOR_KEYS:
        raw = data.get(key)
        if raw:
            try:
                actor_id = UUID(str(raw))
                break
            except (ValueError, TypeError):
                continue

    applied = await InventoryService.deduct_for_treatment(
        db,
        clinic_id=clinic_id,
        catalog_item_id=catalog_item_id,
        treatment_reference_id=(
            UUID(str(data["treatment_id"])) if data.get("treatment_id") else None
        ),
        actor_id=actor_id,
    )
    if applied:
        logger.info(
            "treatment_consumables: auto-deducted %d consumable(s) for treatment %s",
            len(applied),
            data.get("treatment_id"),
        )
