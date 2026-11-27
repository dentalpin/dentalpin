"""Locales the generated PDFs accept (issues #422, #441).

The download buttons send the viewer's UI language, so a PDF endpoint that
only validates ``es|en`` answers 422 in eight of the ten languages the app
ships — a dead button with no message. Every host locale is accepted
instead: labels fall back to English where a module has not translated
them, while amounts and dates still use the locale's own separators.

Both label sets and the Babel locale map live here rather than in one
module, because the list is a property of the host's ``i18n.locales``
(frontend/nuxt.config.ts) and every module that renders a PDF needs the
same one. A test guards the two against each other.

The printed date format lives here too (#1180): every PDF renders its
dates through :func:`format_pdf_date` / :func:`format_pdf_datetime` so a
Hungarian invoice reads ``2026. 11. 26.`` and a German one ``26.11.2026``,
not a fixed ``dd/mm/yyyy``.
"""

from __future__ import annotations

from datetime import date, datetime

PDF_LOCALES: tuple[str, ...] = (
    "es",
    "en",
    "ta",
    "te",
    "hi",
    "fr",
    "pt",
    "pt-BR",
    "de",
    "hu",
    "pl",
    "it",
    "ar",
)
PDF_LOCALE_PATTERN = "^(" + "|".join(PDF_LOCALES) + ")$"

# UI language -> Babel locale for money and dates. Tamil and Telugu clinics are in
# India, so their amounts follow en_IN grouping.
LOCALE_BY_LANG: dict[str, str] = {
    "es": "es_ES",
    "en": "en_US",
    "ta": "en_IN",
    "te": "en_IN",
    "hi": "hi_IN",
    "fr": "fr_FR",
    "pt": "pt_PT",
    "pt-BR": "pt_BR",
    "de": "de_DE",
    "hu": "hu_HU",
    "pl": "pl_PL",
    "it": "it_IT",
    "ar": "ar",
}

# UI language -> strftime pattern for printed dates (#1180). A fixed table
# rather than Babel's ``format_date``: Babel's short patterns use two-digit
# years for some locales and would change the es/en output every existing
# PDF already prints.
DEFAULT_DATE_FORMAT = "%d/%m/%Y"
DATE_FORMAT_BY_LANG: dict[str, str] = {
    "es": "%d/%m/%Y",
    "en": "%d/%m/%Y",
    "ta": "%d/%m/%Y",
    "te": "%d/%m/%Y",
    "hi": "%d/%m/%Y",
    "fr": "%d/%m/%Y",
    "pt": "%d/%m/%Y",
    "pt-BR": "%d/%m/%Y",
    "de": "%d.%m.%Y",
    "hu": "%Y. %m. %d.",
    "pl": "%d.%m.%Y",
    "it": "%d/%m/%Y",
    "ar": "%d/%m/%Y",
}


def pdf_date_format(locale: str) -> str:
    """strftime pattern for a date printed in a ``locale`` PDF."""
    return DATE_FORMAT_BY_LANG.get(locale, DEFAULT_DATE_FORMAT)


def format_pdf_date(value: date, locale: str) -> str:
    """A date (or the date part of a datetime) in the locale's own order."""
    return value.strftime(pdf_date_format(locale))


def format_pdf_datetime(value: datetime, locale: str) -> str:
    """A date followed by ``HH:MM``; convert to the clinic zone first."""
    return value.strftime(f"{pdf_date_format(locale)} %H:%M")
