"""inventory event handlers (#226 core upgrade).

``odontogram.treatment.performed`` → auto-deduction is now handled by
the ``treatment_consumables`` module via subscription inversion (#226):
it owns the links table, resolves links with its own ORM model, and
calls ``InventoryService.apply_consumption`` as a clean public
primitive.  Inventory has no knowledge of treatment_consumables.
"""

from __future__ import annotations

# No event handlers registered in this module — the treatment_performed
# handler lives in treatment_consumables/events.py.
