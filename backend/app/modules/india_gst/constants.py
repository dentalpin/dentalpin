"""Static reference data for India GST: state/UT codes and GSTIN format.

No canonical India-states catalog exists anywhere else in the repo (no
``Patient``/``Clinic`` address is state-structured) — this module owns
its own, since ``place_of_supply``/``clinic_state`` must be compared as
codes, never as free-text display strings.

Codes follow the GST state-code list published in Schedule III /
CBIC's GSTIN structure (first two digits of a GSTIN identify the state).
"""

from __future__ import annotations

import re

# code -> name, per CBIC's state code list (used as the GSTIN prefix).
INDIA_STATES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}

# GSTIN: 2-digit state code, 10-char PAN, 1-digit entity code, "Z", 1
# checksum char. e.g. "33ABCDE1234F1Z7".
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

# Base-36 alphabet the CBIC mod-36 check digit is computed over.
GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Real-world dental SAC (Services Accounting Code) under GST — "Human
# health and social care services". The only SAC that applies to every
# treatment a dental clinic bills, so it doubles as the value the
# autoconfigure action stamps on catalog items that have none yet.
DEFAULT_DENTAL_SAC_CODE = "999312"

REGISTRATION_TYPES = ("regular", "composition", "unregistered", "exempt")


def gstin_checksum_char(first14: str) -> str:
    """CBIC mod-36 check digit over the first 14 GSTIN characters (#262).

    Each character's base-36 value is multiplied by an alternating
    factor (1, 2, 1, 2, …), the product's base-36 digit sum is
    accumulated, and the check digit is the value that rounds the total
    up to a multiple of 36.
    """
    total = 0
    for index, char in enumerate(first14):
        value = GSTIN_ALPHABET.index(char)
        product = value * (2 if index % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_ALPHABET[(36 - total % 36) % 36]


def gstin_format_ok(value: str | None) -> bool:
    """Structural (regex) check only — no checksum."""
    if not value:
        return False
    return bool(GSTIN_PATTERN.match(value.strip().upper()))


def gstin_checksum_ok(value: str) -> bool:
    """True when the 15th character matches the mod-36 check digit.

    Assumes the value already passed :func:`gstin_format_ok`.
    """
    normalized = value.strip().upper()
    return gstin_checksum_char(normalized[:14]) == normalized[14]


def is_valid_gstin(value: str | None) -> bool:
    """Structural format AND mod-36 checksum (#262) — typos are caught
    at input time, not at filing time."""
    if not gstin_format_ok(value):
        return False
    assert value is not None
    return gstin_checksum_ok(value)


def state_name(code: str | None) -> str | None:
    if not code:
        return None
    return INDIA_STATES.get(code)
