"""inventory event handlers (#226 core upgrade).

``odontogram.treatment.performed`` → auto-deduction is now handled by
the ``treatment_consumables`` module via subscription inversion (#226):
it owns the links table, already depends on inventory (no cycle), and
calls ``InventoryService.deduct_for_treatment`` as a clean public
primitive.
"""

from __future__ import annotations

# No event handlers registered in this module — the treatment_performed
# handler lives in treatment_consumables/events.py.
