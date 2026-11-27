"""Fill ``{{ variable }}`` placeholders when a consent is created from a template (#1171).

Substitution is a plain regex over an explicit allowlist: no Jinja, no
filters, no expressions, no attribute access. It runs once, server-side, at
snapshot time, so the professional sees the filled text, can still edit it
while unsigned, and what gets signed is exactly what was shown. Templates
keep the raw ``{{ ... }}`` text.

Values are inserted as plain text: whitespace is collapsed to one line and
Markdown-significant characters are backslash-escaped, so a patient named
``*Ana*`` or ``1. Foo`` cannot inject formatting into ``render_consent_body``
(which already escapes HTML). A missing value becomes a visible ``____`` so
the professional notices and types it while editing.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date

from app.core.pdf_locales import format_pdf_date

BLANK = "____"

VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")

# Allowlist, in the order shown to template authors. Keep in sync with the
# help text (``documents.consent.variablesHelp``) and the module CLAUDE.md.
VARIABLE_NAMES: tuple[str, ...] = (
    "patient_name",
    "patient_id_document",
    "patient_birth_date",
    "clinic_name",
    "professional_name",
    "professional_license",
    "date",
)

_INLINE_SPECIAL = re.compile(r"([\\*_`])")
# A value that starts like a block marker would turn into a heading or list.
_BLOCK_START = re.compile(r"^(#|[-+]|\d{1,9}(?=[.)]))")


def escape_markdown_value(value: str, *, line_start: bool = True) -> str:
    """One line of plain text that renders literally through Markdown.

    ``line_start`` is whether the value lands at the start of a line, where a
    leading ``#``, ``-``, ``+`` or ``1.`` would otherwise open a heading or list.
    """
    text = " ".join(str(value).split())
    text = _INLINE_SPECIAL.sub(r"\\\1", text)
    if not line_start:
        return text
    match = _BLOCK_START.match(text)
    if match is None:
        return text
    if match.group(1).isdigit():
        number = match.group(1)
        return f"{number}\\{text[len(number)]}{text[len(number) + 1 :]}"
    return "\\" + text


def build_values(
    *,
    patient,
    clinic_name: str,
    user,
    today: date,
    locale: str,
) -> dict[str, str | None]:
    """Raw (unescaped) values; ``None`` or empty means "missing"."""
    dob = getattr(patient, "date_of_birth", None)
    return {
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "patient_id_document": getattr(patient, "national_id", None),
        "patient_birth_date": format_pdf_date(dob, locale) if dob else None,
        "clinic_name": clinic_name,
        "professional_name": f"{user.first_name} {user.last_name}",
        "professional_license": getattr(user, "professional_id", None),
        "date": format_pdf_date(today, locale),
    }


def fill_template_variables(text: str, values: Mapping[str, str | None]) -> tuple[str, list[str]]:
    """Return ``(filled_text, unknown_variable_names)``.

    Unknown names are left verbatim and reported once each, in order of
    appearance. Substituted values are never re-scanned.
    """
    unknown: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in VARIABLE_NAMES:
            if name not in unknown:
                unknown.append(name)
            return match.group(0)
        value = values.get(name)
        if value is None or not str(value).strip():
            return BLANK
        line_start = not text[text.rfind("\n", 0, match.start()) + 1 : match.start()].strip()
        return escape_markdown_value(value, line_start=line_start)

    replacer: Callable[[re.Match[str]], str] = replace
    return VARIABLE_PATTERN.sub(replacer, text), unknown
