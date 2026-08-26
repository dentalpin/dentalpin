"""GSTIN mod-36 checksum and state cross-check (#262).

Pure functions — no DB. The two real-world GSTINs below are publicly
listed registrations used only to prove the algorithm against known
check digits.
"""

from __future__ import annotations

import pytest

from app.modules.india_gst.constants import (
    gstin_checksum_char,
    gstin_checksum_ok,
    gstin_format_ok,
    is_valid_gstin,
)

# Publicly known registrations with verified check digits.
REAL_GSTINS = ["27AAPFU0939F1ZV", "29AAACH7409R1ZX"]

# The module's fixture/demo GSTINs — checksum-corrected in #262.
FIXTURE_GSTINS = [
    "33ABCDE1234F1Z7",
    "29ZZZZZ9999Z9ZW",
    "27AABCM9012L1ZC",
    "29AAACK5678H1Z4",
]


@pytest.mark.parametrize("gstin", REAL_GSTINS + FIXTURE_GSTINS)
def test_valid_gstins_pass(gstin: str) -> None:
    assert gstin_format_ok(gstin)
    assert gstin_checksum_ok(gstin)
    assert is_valid_gstin(gstin)


@pytest.mark.parametrize("gstin", REAL_GSTINS)
def test_checksum_char_reproduces_known_digits(gstin: str) -> None:
    assert gstin_checksum_char(gstin[:14]) == gstin[14]


def test_single_character_typo_is_caught() -> None:
    """Any single-character change in the first 14 breaks the checksum."""
    gstin = "27AAPFU0939F1ZV"
    typo = gstin[:5] + ("X" if gstin[5] != "X" else "Y") + gstin[6:]
    assert gstin_format_ok(typo)
    assert not gstin_checksum_ok(typo)
    assert not is_valid_gstin(typo)


def test_wrong_check_digit_is_caught() -> None:
    gstin = "33ABCDE1234F1Z7"
    for wrong in "05AK":
        if wrong == gstin[14]:
            continue
        assert not is_valid_gstin(gstin[:14] + wrong)


def test_lowercase_and_whitespace_are_normalized() -> None:
    assert is_valid_gstin("  33abcde1234f1z7  ")


def test_format_failures_never_reach_the_checksum() -> None:
    assert not is_valid_gstin(None)
    assert not is_valid_gstin("")
    assert not is_valid_gstin("33ABCDE1234F1")  # too short
    assert not is_valid_gstin("33ABCDE1234F105")  # entity code 0 invalid
