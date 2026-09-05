"""Off-books guard: the financial family never touches the settlement axis.

Structural rule (issue #230): financial reports read the INVOICE axis
only. No endpoint may reference recorded/settled amounts or net one
axis against the other. This test scans the family source so the rule
survives refactors — a review note alone would not.

Grandfathered (asserted elsewhere, not here):
``BillingReportService.get_overdue_invoices`` predates the rule.
"""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_TOKENS = (
    "InvoicePayment",
    "allocated",
    "refunded",
    "balance_due",
    "collected",
)

FAMILY_SOURCES = (
    "services/financial.py",
    "tools.py",
)


def _module_root() -> Path:
    return Path(__file__).resolve().parents[3] / "app" / "modules" / "reports"


def test_financial_family_touches_no_settlement_columns():
    root = _module_root()
    offenders: list[str] = []
    for relative in FAMILY_SOURCES:
        text = (root / relative).read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                offenders.append(f"{relative}: {token}")
    assert offenders == [], f"off-books violation: {offenders}"
