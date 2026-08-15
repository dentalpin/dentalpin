"""Pure discount arithmetic shared by every consumer of a budget's prices.

The budget-level ("global") discount is applied by
``BudgetService._recalculate_totals`` to the **VAT-inclusive** sum of
line totals. Anything that needs the discount *per line* (invoice lines,
plan sessions, the from-budget wizard) must prorate it the same way —
this module is the only place that formula lives.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

CENT = Decimal("0.01")


class _LineTotals(Protocol):
    line_subtotal: Decimal
    line_discount: Decimal
    line_total: Decimal
    vat_rate: float


def allocate_global_discount(
    discount_type: str | None,
    discount_value: Decimal | None,
    items: Sequence[_LineTotals],
) -> list[Decimal]:
    """Ex-tax share of the global discount for each item (same order as ``items``).

    * ``percentage`` p: ``share_i = (line_subtotal_i - line_discount_i) * p / 100``.
      Tax scales with the base, so the gross drops by exactly p%.
    * ``absolute`` D (clamped to the gross items total): distributed by each
      line's share of the gross, then divided out of VAT so
      ``Σ (share_i * (1 + vat_i))`` == D. The last item absorbs cent drift.

    Returns zeros when there is no global discount or no items.
    """
    zeros = [Decimal("0.00") for _ in items]
    if not items or not discount_type or not discount_value:
        return zeros

    value = Decimal(str(discount_value))
    if discount_type == "percentage":
        return [
            (
                (Decimal(str(i.line_subtotal)) - Decimal(str(i.line_discount))) * value / 100
            ).quantize(CENT)
            for i in items
        ]

    items_total = sum((Decimal(str(i.line_total)) for i in items), Decimal("0"))
    if items_total <= 0:
        return zeros
    discount = min(value, items_total)
    shares = [
        (
            discount
            * Decimal(str(i.line_total))
            / items_total
            / (1 + Decimal(str(i.vat_rate)) / 100)
        ).quantize(CENT)
        for i in items
    ]
    # ponytail: drift lands on the last line; VAT-weighted largest-remainder if a cent ever matters.
    gross_allocated = sum(
        (s * (1 + Decimal(str(i.vat_rate)) / 100) for s, i in zip(shares, items, strict=True)),
        Decimal("0"),
    )
    last_vat = 1 + Decimal(str(items[-1].vat_rate)) / 100
    shares[-1] = (shares[-1] + (discount - gross_allocated) / last_vat).quantize(CENT)
    return shares


def net_line_amount(item: _LineTotals, global_share: Decimal) -> Decimal:
    """Ex-tax amount the patient actually agreed to pay for a line."""
    return (
        Decimal(str(item.line_subtotal)) - Decimal(str(item.line_discount)) - global_share
    ).quantize(CENT)
