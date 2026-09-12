"""Italian codice fiscale of a natural person (16 characters) with the
check character of DM 23/12/1976, and the partita IVA gate that keeps B2B
invoices out of this module (they are the SDI's, ADR 0025)."""

from __future__ import annotations

import re

_CF_RE = re.compile(
    r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$"
)
_ODD = {
    "0": 1,
    "1": 0,
    "2": 5,
    "3": 7,
    "4": 9,
    "5": 13,
    "6": 15,
    "7": 17,
    "8": 19,
    "9": 21,
    "A": 1,
    "B": 0,
    "C": 5,
    "D": 7,
    "E": 9,
    "F": 13,
    "G": 15,
    "H": 17,
    "I": 19,
    "J": 21,
    "K": 2,
    "L": 4,
    "M": 18,
    "N": 20,
    "O": 11,
    "P": 3,
    "Q": 6,
    "R": 8,
    "S": 12,
    "T": 14,
    "U": 16,
    "V": 10,
    "W": 22,
    "X": 25,
    "Y": 24,
    "Z": 23,
}


def _even(ch: str) -> int:
    return int(ch) if ch.isdigit() else ord(ch) - ord("A")


def normalise_codice_fiscale(raw: str | None) -> str | None:
    """Uppercase 16-char CF with a valid check character, else ``None``."""
    value = "".join(c for c in (raw or "") if c.isalnum()).upper()
    if len(value) != 16 or not _CF_RE.match(value):
        return None
    total = sum(_ODD[c] if i % 2 == 0 else _even(c) for i, c in enumerate(value[:15]))
    if chr(ord("A") + total % 26) != value[15]:
        return None
    return value


def is_partita_iva(raw: str | None) -> bool:
    value = "".join(c for c in (raw or "") if c.isalnum()).upper()
    if value.startswith("IT") and len(value) == 13:
        value = value[2:]
    if len(value) != 11 or not value.isdigit():
        return False
    total = 0
    for i, ch in enumerate(value[:10]):
        n = int(ch)
        if i % 2 == 0:
            total += n
        else:
            n *= 2
            total += n - 9 if n > 9 else n
    return (10 - total % 10) % 10 == int(value[10])
