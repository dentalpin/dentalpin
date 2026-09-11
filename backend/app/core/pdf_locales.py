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
"""

from __future__ import annotations

PDF_LOCALES: tuple[str, ...] = ("es", "en", "ta", "fr", "pt", "de", "hu", "pl", "it", "ar")
PDF_LOCALE_PATTERN = "^(" + "|".join(PDF_LOCALES) + ")$"

# UI language -> Babel locale for money and dates. Tamil clinics are in
# India, so their amounts follow en_IN grouping.
LOCALE_BY_LANG: dict[str, str] = {
    "es": "es_ES",
    "en": "en_US",
    "ta": "en_IN",
    "fr": "fr_FR",
    "pt": "pt_PT",
    "de": "de_DE",
    "hu": "hu_HU",
    "pl": "pl_PL",
    "it": "it_IT",
    "ar": "ar",
}
