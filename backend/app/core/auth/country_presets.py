"""Country presets applied by the first-run setup.

Pure data: currency / timezone / language defaults per ISO-3166 alpha-2
code, plus the bits that make Spain special (NIF/CIF format, the "es"
VAT preset consumed by the catalog module, VeriFactu suggestion).
Anything not listed falls back to :data:`GENERIC` — the client still
lets the user pick currency and timezone by hand.

Core owns this file because ``POST /auth/setup`` lives in core and the
resulting values land on ``clinics`` / ``clinic.settings``. Module-specific
consequences (VAT rates, invoice series, cabinets, hours) are applied by
each module reacting to ``clinic.created`` — never imported from here.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CountryPreset:
    code: str  # ISO2, "" for the generic fallback
    currency: str  # ISO 4217
    timezone: str  # IANA — main zone of the country
    language: str  # es|en|fr|pt|ta|de|hu|pl|it — communication_language default
    vat_preset: str = "generic"  # consumed by catalog: "es" | "generic"
    tax_id_label: str = "Tax ID"
    tax_id_pattern: str | None = None  # server-side format check (normalized upper, no separators)
    tax_id_example: str | None = None
    suggested_modules: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["suggested_modules"] = list(self.suggested_modules)
        return d


# ponytail: one flat table, currency/tz/lang only. Add a column when a second
# country needs real fiscal logic; until then ES is the only "rich" row.
_ROWS: list[tuple[str, str, str, str]] = [
    # EU
    ("AT", "EUR", "Europe/Vienna", "de"),
    ("BE", "EUR", "Europe/Brussels", "fr"),
    ("BG", "BGN", "Europe/Sofia", "en"),
    ("HR", "EUR", "Europe/Zagreb", "en"),
    ("CY", "EUR", "Asia/Nicosia", "en"),
    ("CZ", "CZK", "Europe/Prague", "en"),
    ("DK", "DKK", "Europe/Copenhagen", "en"),
    ("EE", "EUR", "Europe/Tallinn", "en"),
    ("FI", "EUR", "Europe/Helsinki", "en"),
    ("FR", "EUR", "Europe/Paris", "fr"),
    ("DE", "EUR", "Europe/Berlin", "de"),
    ("GR", "EUR", "Europe/Athens", "en"),
    ("HU", "HUF", "Europe/Budapest", "hu"),
    ("IE", "EUR", "Europe/Dublin", "en"),
    ("IT", "EUR", "Europe/Rome", "it"),
    ("LV", "EUR", "Europe/Riga", "en"),
    ("LT", "EUR", "Europe/Vilnius", "en"),
    ("LU", "EUR", "Europe/Luxembourg", "fr"),
    ("MT", "EUR", "Europe/Malta", "en"),
    ("NL", "EUR", "Europe/Amsterdam", "en"),
    ("PL", "PLN", "Europe/Warsaw", "pl"),
    ("PT", "EUR", "Europe/Lisbon", "pt"),
    ("RO", "RON", "Europe/Bucharest", "en"),
    ("SK", "EUR", "Europe/Bratislava", "en"),
    ("SI", "EUR", "Europe/Ljubljana", "en"),
    ("SE", "SEK", "Europe/Stockholm", "en"),
    # Rest of Europe
    ("GB", "GBP", "Europe/London", "en"),
    ("CH", "CHF", "Europe/Zurich", "fr"),
    ("NO", "NOK", "Europe/Oslo", "en"),
    ("AD", "EUR", "Europe/Andorra", "es"),
    # Americas
    ("MX", "MXN", "America/Mexico_City", "es"),
    ("AR", "ARS", "America/Argentina/Buenos_Aires", "es"),
    ("CL", "CLP", "America/Santiago", "es"),
    ("CO", "COP", "America/Bogota", "es"),
    ("PE", "PEN", "America/Lima", "es"),
    ("UY", "UYU", "America/Montevideo", "es"),
    ("EC", "USD", "America/Guayaquil", "es"),
    ("BO", "BOB", "America/La_Paz", "es"),
    ("PY", "PYG", "America/Asuncion", "es"),
    ("VE", "VES", "America/Caracas", "es"),
    ("DO", "DOP", "America/Santo_Domingo", "es"),
    ("CR", "CRC", "America/Costa_Rica", "es"),
    ("PA", "PAB", "America/Panama", "es"),
    ("GT", "GTQ", "America/Guatemala", "es"),
    ("BR", "BRL", "America/Sao_Paulo", "pt"),
    ("US", "USD", "America/New_York", "en"),
    ("CA", "CAD", "America/Toronto", "en"),
    # Others & Middle East / North Africa
    ("SA", "SAR", "Asia/Riyadh", "ar"),
    ("AE", "AED", "Asia/Dubai", "ar"),
    ("EG", "EGP", "Africa/Cairo", "ar"),
    ("QA", "QAR", "Asia/Qatar", "ar"),
    ("KW", "KWD", "Asia/Kuwait", "ar"),
    ("OM", "OMR", "Asia/Muscat", "ar"),
    ("BH", "BHD", "Asia/Bahrain", "ar"),
    ("JO", "JOD", "Asia/Amman", "ar"),
    ("LB", "LBP", "Asia/Beirut", "ar"),
    ("IQ", "IQD", "Asia/Baghdad", "ar"),
    ("MA", "MAD", "Africa/Casablanca", "fr"),
    ("IN", "INR", "Asia/Kolkata", "en"),
    ("AU", "AUD", "Australia/Sydney", "en"),
]

COUNTRY_PRESETS: dict[str, CountryPreset] = {
    code: CountryPreset(code=code, currency=cur, timezone=tz, language=lang)
    for code, cur, tz, lang in _ROWS
}

# Spain — the only country with fiscal logic in v1.
COUNTRY_PRESETS["ES"] = CountryPreset(
    code="ES",
    currency="EUR",
    timezone="Europe/Madrid",
    language="es",
    vat_preset="es",
    tax_id_label="NIF/CIF",
    # DNI (8 digits + letter), NIE (X/Y/Z + 7 digits + letter), CIF (letter +
    # 7 digits + control). Format only — checksum is a client-side warning.
    tax_id_pattern=r"^[A-Z0-9][0-9]{7}[A-Z0-9]$",
    tax_id_example="B12345678",
    suggested_modules=("verifactu",),
)

GENERIC = CountryPreset(code="", currency="EUR", timezone="UTC", language="en")


def get_preset(code: str | None) -> CountryPreset:
    if not code:
        return GENERIC
    return COUNTRY_PRESETS.get(code.upper(), GENERIC)


def normalize_tax_id(value: str) -> str:
    return re.sub(r"[\s\-\.]", "", value).upper()


def tax_id_matches(preset: CountryPreset, value: str) -> bool:
    """True when the preset has no pattern or the normalized value matches it."""
    if not preset.tax_id_pattern:
        return True
    return re.match(preset.tax_id_pattern, normalize_tax_id(value)) is not None
