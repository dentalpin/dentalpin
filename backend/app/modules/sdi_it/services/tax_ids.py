"""Italian fiscal identifiers and the B2B/B2C gate they decide.

``PartitaIva`` (11 digits, Luhn-style check digit) identifies a *soggetto
passivo IVA* — a company, an insurer, a fund, a professional. ``CodiceFiscale``
(16 alphanumerics) identifies a natural person; companies also get a
numeric codice fiscale equal to their partita IVA.

The whole module hinges on one rule (ADR 0025): an invoice whose recipient
is a natural person for healthcare services may **not** go through the
SDI (art. 10-bis DL 119/2018, art. 9-bis DL 135/2018). So the recipient
is "business" only when ``billing_tax_id`` parses as a partita IVA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CF_RE = re.compile(
    r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$"
)


def _compact(raw: str | None) -> str:
    value = "".join(c for c in (raw or "") if c.isalnum()).upper()
    return value[2:] if value.startswith("IT") and len(value) in (13, 18) else value


def partita_iva_check_digit_ok(digits: str) -> bool:
    """Check digit per the Agenzia delle Entrate algorithm (mod-10 variant)."""
    if len(digits) != 11 or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(digits[:10]):
        n = int(ch)
        if i % 2 == 0:
            total += n
        else:
            n *= 2
            total += n - 9 if n > 9 else n
    return (10 - total % 10) % 10 == int(digits[10])


@dataclass(frozen=True)
class PartitaIva:
    value: str  # 11 digits

    @classmethod
    def parse(cls, raw: str | None) -> PartitaIva | None:
        compact = _compact(raw)
        if len(compact) == 11 and compact.isdigit() and partita_iva_check_digit_ok(compact):
            return cls(compact)
        return None


@dataclass(frozen=True)
class CodiceFiscale:
    value: str  # 16 alphanumerics (natural person) or 11 digits (entity)

    @classmethod
    def parse(cls, raw: str | None) -> CodiceFiscale | None:
        compact = _compact(raw)
        if len(compact) == 16 and _CF_RE.match(compact):
            return cls(compact)
        if len(compact) == 11 and compact.isdigit():
            return cls(compact)
        return None

    @property
    def is_natural_person(self) -> bool:
        return len(self.value) == 16


def is_business_recipient(raw_tax_id: str | None) -> bool:
    """True when the id is a valid partita IVA (the SDI gate of ADR 0025)."""
    return PartitaIva.parse(raw_tax_id) is not None
