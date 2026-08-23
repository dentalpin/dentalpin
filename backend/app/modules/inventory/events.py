"""Inventory module event subscribers.

V1: no cross-module event subscriptions.  The module is standalone —
it publishes no events yet and consumes none.  Future consumers:

* ``treatment_consumables`` (issue #225) will consume
  ``inventory.stock_adjusted`` events.
* ``lab_orders`` (issue #221) may consume category data.

Placeholder for the future event catalog entry.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def on_inventory_stock_low(data: dict[str, Any]) -> None:
    """Placeholder — called when an item drops below ``min_quantity``.

    Future use: notify the clinic via notifications module, or surface
    in the copilot daily digest.
    """
    logger.debug(
        "inventory.on_stock_low: item=%s clinic=%s quantity=%s min=%s",
        data.get("item_id"),
        data.get("clinic_id"),
        data.get("quantity"),
        data.get("min_quantity"),
    )
